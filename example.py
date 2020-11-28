from discord.ext import commands
from economy import Economy


bot = commands.Bot(command_prefix='e ', case_insensitive=False)

economy = Economy(bot, items={
    'stick': {},
    'game': {},
    'brain': {}
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

@bot.event
async def on_ready():
    print("Ready")

bot.run("Put your token to test")
