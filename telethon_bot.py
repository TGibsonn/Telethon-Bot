import platform
from datetime import datetime, timedelta
from hashlib import md5
from os import listdir, path
from telethon import RPCError
import telethon.helpers as utils
import telethon.network.authenticator as authenticator
from telethon.errors import *
from telethon.network import MtProtoSender, TcpTransport
from telethon.parser.markdown_parser import parse_message_entities
from telethon.tl import MTProtoRequest, Session
from telethon.tl.all_tlobjects import layer
from telethon.tl.functions import InitConnectionRequest, InvokeWithLayerRequest
from telethon.tl.functions.account import GetPasswordRequest
from telethon.tl.functions.auth import (CheckPasswordRequest, LogOutRequest,
                                        SendCodeRequest, SignInRequest,
                                        SignUpRequest)
from telethon.tl.functions.auth import ImportBotAuthorizationRequest
from telethon.tl.functions.help import GetConfigRequest
from telethon.tl.functions.messages import (SendMessageRequest, GetChatsRequest)
from telethon.tl.functions.contacts import (ResolveUsernameRequest)
from telethon.tl.functions.users import (GetFullUserRequest)
from telethon.tl.types import (InputPeerEmpty, InputPeerChat, InputPeerUser, InputUser)
from telethon.utils import (find_user_or_chat, get_input_peer, get_appropiate_part_size, get_extension)
from telethon.tl.types import UpdateShortChatMessage, UpdateShortMessage

class YolkClient:
    __version__ = '1.0a'
    
    def __init__(self, session, api_id, api_hash, proxy=None):
        if api_id is None or api_hash is None:
            raise PermissionError("Your API ID or Hash are invalid.")
        
        self.api_id = api_id
        self.api_hash = api_hash
        
        if isinstance(session, str):
            self.session = Session.try_load_or_create_new(session)
        elif isinstance(session, Session):
            self.session = session
        else:
            raise ValueError("The given session must be either a string or a Session instance.")
        
        self.transport = TcpTransport(self.session.server_address, self.session.port, proxy)
        
        self.dc_options = None
        self.sender = None
        self.phone_code_hashes = {}
        
        self.signed_in = False
        
    def connect(self, reconnect=False):
        try:
            if not self.session.auth_key or (reconnect and self.sender is not None):
                self.session.auth_key, self.session.time_offset = \
                    authenticator.do_authentication(self.transport)
                
                self.session.save()
            
            self.sender = MtProtoSender(self.transport, self.session)
            
            query = InitConnectionRequest(
                api_id = self.api_id,
                device_model = platform.node(),
                system_version = platform.system(),
                app_version = self.__version__,
                lang_code = "en",
                query = GetConfigRequest())
            
            result = self.invoke(InvokeWithLayerRequest(layer = layer, query = query))
            
            self.dc_options = result.dc_options
            
            self.sender.ack_requests_confirm = True
            
            self.signed_in = self.is_user_authorized()
            
            return True
        except RPCError as error:
            print(f"Could not stabilise initial connection: {error}.")
            return False
        
    def reconnect_to_dc(self, dc_id):
        if self.dc_options is None or not self.dc_options:
            raise ConnectionError("Cannot reconnect. Stabilise an initial connection first.")
        
        dc = next(dc for dc in self.dc_options if dc.id == dc_id)
        
        self.transport.close()
        self.transport = TcpTransport(dc.ip_address, dc.port)
        self.session.server_address = dc.ip_address
        self.session.port = dc.port
        self.session.save()
        
        self.connect(reconnect=True)
    
    def disconnect(self):
        if self.sender:
            self.sender.disconnect()
            self.sender = None
            
    def invoke(self, request, timeout=timedelta(seconds=5), throw_invalid_dc=False):
        if not issubclass(type(request), MTProtoRequest):
            raise ValueError("You can only invoke MtProtoRequests")
        
        try:
            self.sender.send(request)
            self.sender.receive(request, timeout)
            
            return request.result
        
        except InvalidDCError as error:
            if throw_invalid_dc:
                raise error
            
            self.reconnect_to_dc(error.new_dc)
            return self.invoke(request, timeout=timeout, throw_invalid_dc=True)
        
        except RPCError as e:
            print(f"RPC error: {e}")
            print("Continuing...")
            pass
    
    def is_user_authorized(self):
        return self.session.user is not None
    
    def send_code_request(self, phone_number):
        result = self.invoke(SendCodeRequest(phone_number, self.api_id, self.api_hash))
        self.phone_code_hashes[phone_number] = result.phone_code_hash
        
    def sign_in(self, phone_number=None, code=None, password=None, bot_token=None):
        if phone_number and code:
            if phone_number not in self.phone_code_hashes:
                raise ValueError("Please make sure you have called send_code_request first.")
        
            try:
                result = self.invoke(SignInRequest(phone_number, self.phone_code_hashes[phone_number], code))
            except RPCError as error:
                if error.message.startswith("PHONE_CODE_"):
                    print(error)
                    return False
                else:
                    raise error
        
        elif password:
            salt = self.invoke(GetPasswordRequest()).current_salt
            result = self.invoke(CheckPasswordRequest(utils.get_password_hash(password, salt)))
        elif bot_token:
            result = self.invoke(ImportBotAuthorizationRequest(flags = 0,
                                                               api_id = self.api_id,
                                                               api_hash = self.api_hash,
                                                               bot_auth_token = bot_token))
        else:
            raise ValueError("You must provide a phone_number and a code for the first time, "
                             "and a password only if an RPCError was raised before.")
        
        self.session.user = result.user
        self.session.save()
        
        self.signed_in = True
        return True
        
    def sign_up(self, phone_number, code, first_name, last_name=''):
        result = self.invoke(SignUpRequest(phone_number=phone_number,
                                           phone_code_hash=self.phone_code_hash[phone_number],
                                           phone_code=code,
                                           first_name=first_name,
                                           last_name=last_name))
        self.session.user = result.user
        self.session.save()
        
    def log_out(self):
        try:
            self.invoke(LogOutRequest())
            if not self.session.delete():
                return False
                
            self.session = None
        except:
            return False
            
    def send_message(self, peer, message, no_web_page=False, PM=False, access_hash=None):
        msg_id = utils.generate_random_long()
        if not (PM is True):
            self.invoke(SendMessageRequest(peer=InputPeerChat(peer),
                                           message=message,
                                           random_id=msg_id,
                                           no_webpage=no_web_page))
        else:
            if access_hash:
                self.invoke(SendMessageRequest(peer=InputPeerUser(peer, access_hash),
                                               message=message,
                                               random_id=msg_id,
                                               no_webpage=no_web_page))
            else:
                print("Access hash not provided. Could send message to InputPeerUser.")
        return msg_id
    
    def resolve_username(self, username):
        result = self.invoke(ResolveUsernameRequest(username))
        if result:
            return result
        else:
            return "Cannot resolve given username. Ensure provided username is valid."
    
    def get_full_user(self, ID, access_hash):
        result = self.invoke(GetFullUserRequest(InputUser(ID, access_hash)))
        if result:
            return result
        else:
            return "Cannot get full user. Ensure provided ID is valid."
        
    
    def add_update_handler(self, handler):
        if not self.signed_in:
            raise ValueError("You cannot add update handlers until you've signed in.")
        
        self.sender.add_update_handler(handler)

import re

class YolkBot(YolkClient):
    def __init__(self):
        self.session_user_id = "sessionid"
        self.api_hash = "abc123"
        self.api_id = 111111
        self.phone = "+111111111"
        self.proxy = None
        
        self.methods = {
            "resolve_username" : {
                "takes_value" : True,
                "call" : "resolve_username"
            },
            "get_full_user" : {
                "takes_value" : True,
                "call" : "full_user"
            },
        }
        
        super().__init__(self.session_user_id, self.api_id, self.api_hash, self.proxy)
        
        print("Connecting to Telegram servers. Please wait...")
        
        self.connect()
        
        self.check_auth()
        
        self.run()
        
    def check_auth(self):
        if not self.is_user_authorized():
            print("Code required.")
            
            self.send_code_request(self.phone)
            
            code_ok = False
            while not code_ok:
                code = input("Enter code received: ")
                try:
                    code_ok = self.sign_in(self.phone, code)
                except RPCError as e:
                    raise e

    def full_user(self, username):
        id = self.resolve_username(username).users[0].id
        access_hash = self.resolve_username(username).users[0].access_hash
        return self.get_full_user(id, access_hash)
    
    def parse_method(self, command):
        try:
            method = re.search("Yolk\((.+?)\)", command)
            return method.group(1)
        except AttributeError:
            return None
            pass
    
    def parse_value(self, command):
        if "=" in command:
            try:
                value = (command.split("=", 1)[1].strip())
                if "," in value:
                    value = value.split(", ")
                    return value
                else:
                    return [value]
            except:
                return None
                pass
        else:
            return None
        
    def handle_command(self, command, update_object):
        method = self.parse_method(command)
        value = self.parse_value(command)
        if method in self.methods:
            call = self.methods.get(method, {}).get("call")
            takes_value = self.methods.get(method, {}).get("takes_value")
            if takes_value and not value:
                self.send_message(update_object.chat_id, f"{method} requires a value. Try again.")
            elif takes_value and value:
                result = getattr(self, call)(*value)
                return result
                print(f"Completed {method} with {value}.")
            elif not takes_value:
                result = getattr(self, call)
                return result
                print(f"Completed {method}.")
        else:
            self.send_message(update_object.chat_id, f"{method} is not a valid method.")
    
    def command_handler(self, update_object):
        if type(update_object) is UpdateShortChatMessage:
            
            # Replace the value after the '==' with the chat ID you want to restrict the chat to.
            
            if "Yolk(" in update_object.message and update_object.chat_id == 101010101:
                command = update_object.message
                self.send_message(update_object.chat_id, str(self.handle_command(command, update_object)))
    
    def pm_listener(self, update_object):
        if type(update_object) is UpdateShortMessage:
            print(f"Received PM from {update_object.user_id}")
            if update_object.user_id == 342379009:
                self.send_message(update_object.user_id, "I am currently running without issue.", PM=True, access_hash=-8299841778433488371)
                
    
    def run(self):
        
        # Add update handlers here.
        self.add_update_handler(self.pm_listener)
        self.add_update_handler(self.command_handler)
        
        
        while True:
            while True:
                msg = input("")
    

bot = YolkBot()
