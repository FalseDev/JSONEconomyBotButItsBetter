from discord.ext import commands
from economy import Economy


bot = commands.Bot(command_prefix=lambda _1,_2:['e ', 'E '])

economy = Economy(bot, items={
    'stick': {'price': 10},
    'game': {'price': 100},
    'brain': {'price': 1000}
})

bot.add_cog(economy)

bot.load_extension('jishaku')


# Your function name must be use_item_name
# For eg, the function to use a stick will be use_stick
# This will make stick a usable item
# While brain won't be usable as it doesn't have a use-function :)
@economy.use_item()
async def use_stick(ctx: commands.Context):
    await ctx.send("You used a stick, lol")


# OR you can pass the target item as an arg like this
@economy.use_item("game")
async def any_name(ctx: commands.Context):
    await ctx.send("You played a game and lost :(")


# Setup a custom handler when a user enters an invalid item
@economy.event()
async def on_invalid_item(ctx: commands.Context, item_name: str):
    await ctx.send(f"What are you thinking man? {item_name} is not even in the shop")

@bot.event
async def on_ready():
    print("Ready")

bot.run("Put your token to test")
