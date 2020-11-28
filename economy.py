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
        bank_data_file: Optional[str] = 'bank_data.json',
        balance_field_name: Optional[str] = "balance",
        inventory_field_name: Optional[str] = 'inventory',
        default_balance: Optional[int] = 500,
        default_inventory: Optional[dict] = {},
    ):

        self.bot = bot
        self.items = items
        self.use_functions = use_functions
        self.ready = False

        # Cutomizations here
        self.bank_data_file = bank_data_file
        self.balance_field_name = balance_field_name
        self.inventory_field_name = inventory_field_name
        self.default_balance = default_balance
        self.default_inventory = default_inventory

        asyncio.ensure_future(self.load_json_data())

    # Cog functions
    def cog_check(self, ctx: commands.Context):
        if str(ctx.author.id) not in self.accounts:
            self.accounts.update({
                str(ctx.author.id): self.get_starter_account()
            })
        return self.ready

    def cog_unload(self):
        asyncio.run(self.save_json_data())

    # Loading and saving
    async def load_json_data(self):
        async with aiofiles.open(self.bank_data_file, mode='r') as f:
            content = await f.read()
        self.data = json.loads(content)
        self.accounts = self.data['accounts']
        self.ready = True
        print("Economy system ready!")

    async def save_json_data(self, filename: Optional[str] = None):
        async with aiofiles.open(filename or self.bank_data_file, mode='w') as f:
            await f.write(json.dumps(self.data, indent=4, sort_keys=True))

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
            self.balance_field_name: self.default_balance,
            self.inventory_field_name: self.default_inventory
        }

    async def get_inv(self, user_id: int):
        user = self.accounts[str(user_id)]
        return user[self.inventory_field_name]

    async def change_item_quantity(self, user_id: int, item_name: str, amount: int):
        """Change the quantity of an item in a person's inventory"""
        inventory = await self.get_inv(user_id)

        if amount < 0:
            if item_name not in inventory:
                return 0
            if inventory[item_name] < amount:
                return inventory[item_name]

        inventory[item_name] += amount
        if inventory[item_name] == 0:
            inventory.pop(item_name)
        return True

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
    async def use(self, ctx: commands.Context, item_name):
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

        consumed = await self.change_item_quantity(ctx.author.id, item_name, -1)

        if consumed is not True:
            return await self.on_no_items(ctx, item_name)

        await self.use_functions[item_name](ctx)

    # Boilerplate event handlers
    @staticmethod
    async def on_invalid_item(ctx: commands.Context, item_name: str):
        await ctx.send(f"{item_name} is not a valid item")

    @staticmethod
    async def on_unusable_item(ctx: commands.Context, item_name: str):
        await ctx.send(f"{item_name} is not a usable item")

    @staticmethod
    async def on_no_items(ctx: commands.Context, item_name: str):
        await ctx.send(f"You have 0 of {item_name}, oops")


def setup(bot: commands.Bot):
    bot.add_cog(Economy(bot))
