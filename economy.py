import asyncio
import json
import traceback
from typing import Callable, List, Optional

import aiofiles
from discord.ext import commands
from discord import Member


class ImproperUseFunctionName(Exception):
    """Error thrown when the name of an item-use function is not valid"""


class Economy(commands.Cog):
    def __init__(
        self, bot,  # Defaults
        items={}, use_functions={},  # Mappers
        bank_data_file: str = 'bank_data.json',

        wallet_field_name: str = "wallet",
        default_wallet_balance: int = 500,

        inventory_field_name: str = 'inventory',
        default_inventory: dict = {},

        bank_field_name: str = "bank",
        default_bank_capacity: int = 0,
        default_bank_balance: int = 0,
    ):

        self.bot = bot
        self.items = items
        self.use_functions = use_functions
        self.ready = False
        self._bank_lock = asyncio.Lock()

        # Cutomizations here
        self.bank_data_file = bank_data_file
        self.wallet_field_name = wallet_field_name
        self.default_wallet_balance = default_wallet_balance

        self.inventory_field_name = inventory_field_name
        self.default_inventory = default_inventory

        self.bank_field_name = bank_field_name
        self.default_bank_capacity = default_bank_capacity
        self.default_bank_balance = default_bank_balance

        asyncio.ensure_future(self.load_json_data())

    # Cog functions
    def cog_check(self, ctx: commands.Context):
        if str(ctx.author.id) not in self.accounts:
            self.accounts.update({
                str(ctx.author.id): self.get_starter_account()
            })
        return self.ready

    def cog_unload(self):
        # TODO: This isn't working as expected
        asyncio.run(self.save_json_data())

    # Loading and saving
    async def load_json_data(self):
        async with self._bank_lock:
            async with aiofiles.open(self.bank_data_file, mode='r') as f:
                content = await f.read()
        self.data = json.loads(content)
        self.accounts = self.data['accounts']
        self.ready = True
        print("Economy system ready!")

    async def save_json_data(self, filename: Optional[str] = None):
        async with self._bank_lock:
            async with aiofiles.open(filename or self.bank_data_file, mode='w') as f:
                await f.write(json.dumps(self.data, indent=4, sort_keys=True))
        print(f"Saved bank data into {filename}")

    # Admin commands
    @commands.command(name="savedata")
    @commands.is_owner()
    async def save_data(self, ctx: commands.Context):
        await self.save_json_data()
        await ctx.send("Done!")

    @commands.command(name="loaddata")
    @commands.is_owner()
    async def load_data(self, ctx: commands.Context):
        self.ready = False
        await self.load_json_data()
        await ctx.send("Done!")

    # Helpers
    def get_starter_account(self):
        return {
            self.wallet_field_name: self.default_wallet_balance,
            self.inventory_field_name: self.default_inventory,
            self.bank_field_name: {
                "capacity": self.default_bank_capacity,
                "balance": self.default_bank_balance
            }
        }

    async def get_account(self, user_id: int):
        return self.accounts.get(str(user_id))

    async def get_inv(self, user_id: int):
        user = await self.get_account(user_id)
        if user is None:
            return
        return user[self.inventory_field_name]

    async def get_bank(self, user_id: int):
        user = await self.get_account(user_id)
        if user is None:
            return
        return user[self.bank_field_name]

    async def change_item_quantity(self, user_id: int, item_name: str, amount: int):
        """Change the quantity of an item in a person's inventory
        Returns `False` and number of items in inventory if there's not enough to decrease
        Returns `True` and number of items in inventory on success"""
        inventory = await self.get_inv(user_id)

        if amount < 0:
            if item_name not in inventory:
                return False, 0
            if inventory[item_name] < amount:
                return False, inventory[item_name]

        if item_name not in inventory:
            inventory[item_name] = 0

        inventory[item_name] += amount
        quantity = inventory[item_name]
        if inventory[item_name] == 0:
            inventory.pop(item_name)
        return True, quantity

    async def change_wallet_balance(self, user_id: int, amount: int):
        """Returns a tuple of success, wallet-balance, bank-balance"""
        user = await self.get_account(user_id)
        if user is None:
            return None, None, None

        if amount < 0:
            if user[self.wallet_field_name] < -amount:
                return False, user[self.wallet_field_name], user[self.bank_field_name]['balance']

        user[self.wallet_field_name] += amount
        return True, user[self.wallet_field_name], user[self.bank_field_name]['balance']

    # Decorators
    def use_item(self, item_name: Optional[str] = None):
        """Add a use-item function for the corresponding `item_name`"""
        def predicate(func: Callable):
            nonlocal item_name
            if item_name is None:
                if not (len(func.__name__) > 4 and func.__name__.startswith('use_')):
                    raise ImproperUseFunctionName(
                        f"{func.__name__} is an invalid name for a use function")
                item_name = func.__name__[4:]

            self.use_functions.update({item_name: func})
        return predicate

    # Commands
    @commands.command(name="use")
    async def use(self, ctx: commands.Context, item_name: str):
        """
        Consume an item
        """
        item_name = item_name.lower()
        if not item_name in self.use_functions:
            return (
                await self.on_invalid_item(ctx, item_name)
                if not item_name in self.items
                else await self.on_unusable_item(ctx, item_name)
            )

        consumed, _ = await self.change_item_quantity(ctx.author.id, item_name, -1)

        if consumed is not True:
            return await self.on_no_items(ctx, item_name)

        await self.use_functions[item_name](ctx)

    @commands.command(name="buy")
    async def buy(self, ctx: commands.Context, item_name: str, quantity: int = 1):
        item_name = item_name.lower()
        if item_name not in self.items:
            return await self.on_invalid_item(ctx, item_name)

        item = self.items[item_name]
        price = item['price']
        cost = price*quantity

        bought, wallet_bal, bank_bal = await self.change_wallet_balance(
            ctx.author.id, -cost)

        if not bought:
            return await self.on_not_enough_in_wallet(ctx, cost, wallet_bal, bank_bal)

        _, total = await self.change_item_quantity(ctx.author.id, item_name, quantity)

        await self.on_bought(ctx, item_name, quantity, total, wallet_bal, bank_bal)

    # Basic event handlers
    @staticmethod
    async def on_invalid_item(ctx: commands.Context, item_name: str):
        await ctx.send(f"{item_name} is not a valid item")

    @staticmethod
    async def on_unusable_item(ctx: commands.Context, item_name: str):
        await ctx.send(f"{item_name} is not a usable item")

    @staticmethod
    async def on_no_items(ctx: commands.Context, item_name: str):
        await ctx.send(f"You have 0 of {item_name}, oops")

    @staticmethod
    async def on_not_enough_in_wallet(ctx: commands.Context, required: int, wallet: int, bank: int):
        await ctx.send(
            f"You have only {wallet}, but you need {required}, maybe withdraw some from the {bank} in you bank")

    @staticmethod
    async def on_bought(ctx: commands.Context, item_name: str, bought_quantity: int, total: int, wallet: int, bank: int):
        await ctx.send(
            f"You bought {bought_quantity} {item_name}, now you have {total} {item_name}, {wallet} in wallet and {bank} in bank")


def setup(bot: commands.Bot):
    bot.add_cog(Economy(bot))
