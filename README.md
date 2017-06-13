# Telethon-Bot
A functional bot that uses Telethon to communicate with Telegram's MTProto API.

# Requirements
You will need a Telethon to be installed which you can receive here: https://github.com/LonamiWebs/Telethon

# Example commands
Yolk(resolve_username) = username

This will resolve the username of a specified user using method resolve_username with value "username".

You can add additional methods through the methods dictionary specified in the YolkBot class and specify the method in the YolkClient class for use.

# Handlers
Update handlers can be simply added within the run method via add_update_handler(method with listener logic). You can refer to the pm_listener method as an example.

# Setup
You'll need to replace the api_id, phone and api_hash with your Telegram API information as well as the phone (can be Google Voice) for your bot. You'll also need to change the value in the command_handler method in order for it to listen to commands for your specific group. You can remove it entirely if you want it to universally listen for commands.

# Getting an access hash for PM
In order to get the access hash, you will need to resolve the username and retrieve the access hash from the output. I've filled it with my own which allows it to respond to my PM. These hashes are public and can be retrieved from any username. You can do this automatically once you receive a PM but that hasn't been set up. It will still listen for PMs, however.

# Purpose
This project is meant to demonstrate what can be done using Telethon's API wrapper and perhaps be a starting point for your project. 

# Invoking custom requests to MTProto
The functions and types you can use from Telethon are automatically generated within the Telethon folder. You can clone the git repository and run python3 tl_generator.py. This should generate all the MTProto requests and types necessary.
