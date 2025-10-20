import os
import sys
import time
import json
import threading
from datetime import datetime
import hmac
import hashlib
import requests
import string
import random
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser
import codecs
import urllib3
from pymongo import MongoClient
from flask import Flask, jsonify

# Disable only the InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Flask App
app = Flask(__name__)

# MongoDB setup
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "freefire_accounts"
COLLECTION_NAME = "accounts"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
accounts_collection = db[COLLECTION_NAME]

# Original script constants
hex_key = "32656534343831396539623435393838343531343130363762323831363231383734643064356437616639643866376530306331653534373135623764316533"
key = bytes.fromhex(hex_key)

REGION_LANG = {"ME": "ar","IND": "hi","ID": "id","VN": "vi","TH": "th","BD": "bn","PK": "ur","TW": "zh","EU": "en","CIS": "ru","NA": "en","SAC": "es","BR": "pt"}
REGION_URLS = {"IND": "https://client.ind.freefiremobile.com","ID": "https://clientbp.ggblueshark.com/","BR": "https://client.us.freefiremobile.com/","ME": "https://clientbp.common.ggbluefox.com/","VN": "https://clientbp.ggblueshark.com/","TH": "https://clientbp.common.ggbluefox.com/","CIS": "https://clientbp.ggblueshark.com/","BD": "https://clientbp.ggblueshark.com/","PK": "https://clientbp.ggblueshark.com/","SG": "https://clientbp.ggblueshark.com/","NA": "https://client.us.freefiremobile.com/","SAC": "https://client.us.freefiremobile.com/","EU": "https://clientbp.ggblueshark.com/","TW": "https://clientbp.ggblueshark.com/"}

def get_region(language_code: str) -> str:
    return REGION_LANG.get(language_code)

def get_region_url(region_code: str) -> str:
    """Return URL for a given region code"""
    return REGION_URLS.get(region_code, None)

def EnC_Vr(N):
    if N < 0: ''
    H = []
    while True:
        BesTo = N & 0x7F ; N >>= 7
        if N: BesTo |= 0x80
        H.append(BesTo)
        if not N: break
    return bytes(H)
    
def DEc_Uid(H):
    n = s = 0
    for b in bytes.fromhex(H):
        n |= (b & 0x7F) << s
        if not b & 0x80: break
        s += 7
    return n
    
def CrEaTe_VarianT(field_number, value):
    field_header = (field_number << 3) | 0
    return EnC_Vr(field_header) + EnC_Vr(value)

def CrEaTe_LenGTh(field_number, value):
    field_header = (field_number << 3) | 2
    encoded_value = value.encode() if isinstance(value, str) else value
    return EnC_Vr(field_header) + EnC_Vr(len(encoded_value)) + encoded_value

def CrEaTe_ProTo(fields):
    packet = bytearray()    
    for field, value in fields.items():
        if isinstance(value, dict):
            nested_packet = CrEaTe_ProTo(value)
            packet.extend(CrEaTe_LenGTh(field, nested_packet))
        elif isinstance(value, int):
            packet.extend(CrEaTe_VarianT(field, value))           
        elif isinstance(value, str) or isinstance(value, bytes):
            packet.extend(CrEaTe_LenGTh(field, value))           
    return packet

def E_AEs(Pc):
    Z = bytes.fromhex(Pc)
    key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    K = AES.new(key , AES.MODE_CBC , iv)
    R = K.encrypt(pad(Z , AES.block_size))
    return bytes.fromhex(R.hex())

def generate_random_name():
    characters = string.ascii_letters + string.digits
    name = 'LADY-'+''.join(random.choice(characters) for _ in range(6)).upper()
    return name

def generate_custom_password(random_length=9):
    characters = string.ascii_letters + string.digits
    random_part = ''.join(random.choice(characters) for _ in range(random_length)).upper()
    return f"Lady-{random_part}"

def create_acc(region, proxy=None):
    password = generate_custom_password()
    data = f"password={password}&client_type=2&source=2&app_id=100067"
    message = data.encode('utf-8')
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()

    url = "https://100067.connect.garena.com/oauth/guest/register"

    headers = {
        "User-Agent": "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)",
        "Authorization": "Signature " + signature,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive"
    }
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        response = requests.post(url, headers=headers, data=data, proxies=proxies, verify=False, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        uid = response.json()['uid']
        return token(uid, password, region, proxy)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Erro ao criar conta (create_acc) com proxy {proxy}: {e}")
        return None
    except KeyError:
        print(f"[ERROR] 'uid' não encontrado na resposta de create_acc com proxy {proxy}. Resposta: {response.text}")
        return None

def token(uid , password , region, proxy=None):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"

    headers = {
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)",
    }

    body = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": key,
        "client_id": "100067"
    }
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        response = requests.post(url, headers=headers, data=body, proxies=proxies, verify=False, timeout=10)
        response.raise_for_status()
        open_id = response.json()['open_id']
        access_token = response.json()["access_token"]
        refresh_token = response.json()['refresh_token']
        
        result = encode_string(open_id)
        field = to_unicode_escaped(result['field_14'])
        field = codecs.decode(field, 'unicode_escape').encode('latin1')
        return Major_Regsiter(access_token , open_id , field, uid, password, region, proxy)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Erro ao obter token (token) com proxy {proxy}: {e}")
        return None
    except KeyError:
        print(f"[ERROR] Chave não encontrada na resposta de token com proxy {proxy}. Resposta: {response.text}")
        return None

def encode_string(original):
    keystream = [
    0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37, 0x30,
    0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37,
    0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31,
    0x37, 0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30
    ]
    encoded = ""
    for i in range(len(original)):
        orig_byte = ord(original[i])
        key_byte = keystream[i % len(keystream)]
        result_byte = orig_byte ^ key_byte
        encoded += chr(result_byte)
    return {
        "open_id": original,
        "field_14": encoded
        }

def to_unicode_escaped(s):
    """Convert string to Python-style Unicode escaped string"""
    return ''.join(
        c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}'
        for c in s
    )

def Major_Regsiter(access_token , open_id , field , uid , password,region, proxy=None):
    url = "https://loginbp.ggblueshark.com/MajorRegister"
    name = generate_random_name()

    headers = {
        "Accept-Encoding": "gzip",
        "Authorization": "Bearer",   
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "Host": "loginbp.ggblueshark.com",
        "ReleaseVersion": "OB50",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
        "X-GA": "v1 1",
        "X-Unity-Version": "2018.4."
    }

    payload = {
        1: name,
        2: access_token,
        3: open_id,
        5: 102000007,
        6: 4,
        7: 1,
        13: 1,
        14: field,
        15: "en",
        16: 1,
        17: 1

    }

    payload = CrEaTe_ProTo(payload).hex()
    payload = E_AEs(payload).hex()
    body = bytes.fromhex(payload)
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        response = requests.post(url, headers=headers, data=body, proxies=proxies, verify=False, timeout=10)
        response.raise_for_status()
        return login(uid , password, access_token , open_id , response.content.hex() , response.status_code , name , region, proxy)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Erro no Major_Regsiter com proxy {proxy}: {e}")
        return None

def encrypt_api(plain_text):
    plain_text = bytes.fromhex(plain_text)
    key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    cipher_text = cipher.encrypt(pad(plain_text, AES.block_size))
    return cipher_text.hex()

def chooseregion(data_bytes, jwt_token, proxy=None):
    url = "https://loginbp.ggblueshark.com/ChooseRegion"
    payload = data_bytes
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 12; M2101K7AG Build/SKQ1.210908.001)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/x-www-form-urlencoded",
        'Expect': "100-continue",
        'Authorization': f"Bearer {jwt_token}",
        'X-Unity-Version': "2018.4.11f1",
        'X-GA': "v1 1",
        'ReleaseVersion': "OB50"
    }
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        response = requests.post(url, data=payload, headers=headers, proxies=proxies, verify=False, timeout=10)
        response.raise_for_status()
        return response.status_code
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Erro em chooseregion com proxy {proxy}: {e}")
        return None

def login(uid , password, access_token , open_id, response_hex , status_code , name , region, proxy=None):
    
    lang = get_region(region)
    lang_b = lang.encode("ascii")
    headers = {
        "Accept-Encoding": "gzip",
        "Authorization": "Bearer",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "Host": "loginbp.ggblueshark.com",
        "ReleaseVersion": "OB50",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
        "X-GA": "v1 1",
        "X-Unity-Version": "2018.4.11f1"
    }

    payload_template = b'\x1a\x132025-08-30 05:19:21"\tfree fire(\x01:\x081.114.13B2Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)J\x08HandheldR\nATM MobilsZ\x04WIFI`\xb6\nh\xee\x05r\x03300z\x1fARMv7 VFPv3 NEON VMH | 2400 | 2\x80\x01\xc9\x0f\x8a\x01\x0fAdreno (TM) 640\x92\x01\rOpenGL ES 3.2\x9a\x01+Google|dfa4ab4b-9dc4-454e-8065-e70c733fa53f\xa2\x01\x0e105.235.139.91\xaa\x01\x02' + lang_b + b'\xb2\x01 1d8ec0240ede109973f3321b9354b44d\xba\x01\x014\xc2\x01\x08Handheld\xca\x01\x10Asus ASUS_I005DA\xea\x01@afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390\xf0\x01\x01\xca\x02\nATM Mobils\xd2\x02\x04WIFI\xca\x03 7428b253defc164018c604a1ebbfebdf\xe0\x03\xa8\x81\x02\xe8\x03\xf6\xe5\x01\xf0\x03\xaf\x13\xf8\x03\x84\x07\x80\x04\xe7\xf0\x01\x88\x04\xa8\x81\x02\x90\x04\xe7\xf0\x01\x98\x04\xa8\x81\x02\xc8\x04\x01\xd2\x04=/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/lib/arm\xe0\x04\x01\xea\x04_2087f61c19f57f2af4e7feff0b24d9d9|/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/base.apk\xf0\x04\x03\xf8\x04\x01\x8a\x05\x0232\x9a\x05\n2019118692\xb2\x05\tOpenGLES2\xb8\x05\xff\x7f\xc0\x05\x04\xe0\x05\xf3F\xea\x05\x07android\xf2\x05pKqsHT5ZLWrYljNb5Vqh//yFRlaPHSO9NWSQsVvOmdhEEn7W+VHNUK+Q+fduA3ptGB0Ll0LRz3WW0jOwesLj6aiU7sZ40p8BfUE/FI/jzSTwRe2\xf8\x05\xfb\xe4\x06\x88\x06\x01\x90\x06\x01\x9a\x06\x014\xa2\x06\x014\xb2\x06"GQ@O\x00\x0e^\x00D\x06UA\x0ePM\r\x13hZ\x07T\x06\x0cm\\V\x0ejYV;\x0bU5'''

    data = payload_template
    data = data.replace(b'afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390',access_token.encode())
    data = data.replace(b'1d8ec0240ede109973f3321b9354b44d',open_id.encode())
    d = encrypt_api(data.hex())
    
    Final_Payload = bytes.fromhex(d)
    if region.lower() == "me":
        URL = "https://loginbp.common.ggbluefox.com/MajorLogin"
    else:
        URL = "https://loginbp.ggblueshark.com/MajorLogin"
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        RESPONSE = requests.post(URL, headers=headers, data=Final_Payload, proxies=proxies, verify=False, timeout=10)
        RESPONSE.raise_for_status()

        if len(RESPONSE.text) < 10:
            print(f"[WARN] Resposta curta do MajorLogin com proxy {proxy}. Status: {RESPONSE.status_code}")
            return None
        
        if lang.lower() not in ["ar", "en"]:
            json_result = get_available_room(RESPONSE.content.hex())
            if json_result:
                parsed_data = json.loads(json_result)
                BASE64_TOKEN = parsed_data['8']['data']
                print(f"[INFO] BASE64_TOKEN (chooseregion): {BASE64_TOKEN}")

                if region.lower() == "cis":
                    region = "RU"
                fields = {1:region}
                
                fields = bytes.fromhex(encrypt_api(CrEaTe_ProTo(fields).hex()))
                r = chooseregion(fields, BASE64_TOKEN, proxy)
                if r == 200:
                    return login_server(uid , password, access_token , open_id, response_hex , status_code , name , region, proxy)
                else:
                    print(f"[ERROR] Falha ao escolher região com proxy {proxy}. Status: {r}")
                    return None
            else:
                print(f"[ERROR] Falha ao obter json_result de get_available_room com proxy {proxy}.")
                return None
        else:
            BASE64_TOKEN = RESPONSE.text[RESPONSE.text.find("eyJhbGciOiJIUzI1NiIsInN2ciI6IjEiLCJ0eXAiOiJKV1QifQ"):-1]
        second_dot_index = BASE64_TOKEN.find(".", BASE64_TOKEN.find(".") + 1)     
        time.sleep(0.2)
        BASE64_TOKEN = BASE64_TOKEN[:second_dot_index+44]
        dat = GET_PAYLOAD_BY_DATA(BASE64_TOKEN,access_token,1,response_hex , status_code , name , uid , password,region, proxy)
        return dat
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Erro no login (MajorLogin) com proxy {proxy}: {e}")
        return None
    except KeyError:
        print(f"[ERROR] Chave não encontrada na resposta de login (MajorLogin) com proxy {proxy}. Resposta: {RESPONSE.text}")
        return None

def login_server(uid , password, access_token , open_id, response_hex , status_code , name , region, proxy=None):
    lang = get_region(region)
    lang_b = lang.encode("ascii")

    headers = {
        "Accept-Encoding": "gzip",
        "Authorization": "Bearer",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Expect": "100-continue",
        "Host": "loginbp.ggblueshark.com",
        "ReleaseVersion": "OB50",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_I005DA Build/PI)",
        "X-GA": "v1 1",
        "X-Unity-Version": "2018.4.11f1"
    }    

    payload_template = b'\x1a\x132025-08-30 05:19:21"\tfree fire(\x01:\x081.114.13B2Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)J\x08HandheldR\nATM MobilsZ\x04WIFI`\xb6\nh\xee\x05r\x03300z\x1fARMv7 VFPv3 NEON VMH | 2400 | 2\x80\x01\xc9\x0f\x8a\x01\x0fAdreno (TM) 640\x92\x01\rOpenGL ES 3.2\x9a\x01+Google|dfa4ab4b-9dc4-454e-8065-e70c733fa53f\xa2\x01\x0e105.235.139.91\xaa\x01\x02' + lang_b + b'\xb2\x01 1d8ec0240ede109973f3321b9354b44d\xba\x01\x014\xc2\x01\x08Handheld\xca\x01\x10Asus ASUS_I005DA\xea\x01@afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390\xf0\x01\x01\xca\x02\nATM Mobils\xd2\x02\x04WIFI\xca\x03 7428b253defc164018c604a1ebbfebdf\xe0\x03\xa8\x81\x02\xe8\x03\xf6\xe5\x01\xf0\x03\xaf\x13\xf8\x03\x84\x07\x80\x04\xe7\xf0\x01\x88\x04\xa8\x81\x02\x90\x04\xe7\xf0\x01\x98\x04\xa8\x81\x02\xc8\x04\x01\xd2\x04=/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/lib/arm\xe0\x04\x01\xea\x04_2087f61c19f57f2af4e7feff0b24d9d9|/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/base.apk\xf0\x04\x03\xf8\x04\x01\x8a\x05\x0232\x9a\x05\n2019118692\xb2\x05\tOpenGLES2\xb8\x05\xff\x7f\xc0\x05\x04\xe0\x05\xf3F\xea\x05\x07android\xf2\x05pKqsHT5ZLWrYljNb5Vqh//yFRlaPHSO9NWSQsVvOmdhEEn7W+VHNUK+Q+fduA3ptGB0Ll0LRz3WW0jOwesLj6aiU7sZ40p8BfUE/FI/jzSTwRe2\xf8\x05\xfb\xe4\x06\x88\x06\x01\x90\x06\x01\x9a\x06\x014\xa2\x06\x014\xb2\x06"GQ@O\x00\x0e^\x00D\x06UA\x0ePM\r\x13hZ\x07T\x06\x0cm\\V\x0ejYV;\x0bU5'''

    data = payload_template
    data = data.replace(b'afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390',access_token.encode())
    data = data.replace(b'1d8ec0240ede109973f3321b9354b44d',open_id.encode())
    d = encrypt_api(data.hex())
    
    Final_Payload = bytes.fromhex(d)
    if region.lower() == "me":
        URL = "https://loginbp.common.ggbluefox.com/MajorLogin"
    else:
        URL = "https://loginbp.ggblueshark.com/MajorLogin"
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        RESPONSE = requests.post(URL, headers=headers, data=Final_Payload, proxies=proxies, verify=False, timeout=10)
        RESPONSE.raise_for_status()

        if len(RESPONSE.text) < 10:
            print(f"[WARN] Resposta curta do MajorLogin (login_server) com proxy {proxy}. Status: {RESPONSE.status_code}")
            return None

        json_result = get_available_room(RESPONSE.content.hex())
        if json_result:
            parsed_data = json.loads(json_result)
            BASE64_TOKEN = parsed_data['8']['data']

            second_dot_index = BASE64_TOKEN.find(".", BASE64_TOKEN.find(".") + 1)     
            time.sleep(0.2)
            BASE64_TOKEN = BASE64_TOKEN[:second_dot_index+44]
            print(f"[INFO] BASE64_TOKEN (login_server): {BASE64_TOKEN}")
            dat = GET_PAYLOAD_BY_DATA(BASE64_TOKEN,access_token,1,response_hex , status_code , name , uid , password, region, proxy)
            return dat
        else:
            print(f"[ERROR] Falha ao obter json_result de get_available_room (login_server) com proxy {proxy}.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Erro no login_server com proxy {proxy}: {e}")
        return None
    except KeyError:
        print(f"[ERROR] Chave não encontrada na resposta de login_server com proxy {proxy}. Resposta: {RESPONSE.text}")
        return None

import base64
def GET_PAYLOAD_BY_DATA(JWT_TOKEN, NEW_ACCESS_TOKEN, date,response_hex , status_code , name, uid, password, region, proxy=None):
        try:
            token_payload_base64 = JWT_TOKEN.split('.')[1]
            token_payload_base64 += '=' * ((4 - len(token_payload_base64) % 4) % 4)
            decoded_payload = base64.urlsafe_b64decode(token_payload_base64).decode('utf-8')
            decoded_payload = json.loads(decoded_payload)
            NEW_EXTERNAL_ID = decoded_payload['external_id']
            SIGNATURE_MD5 = decoded_payload['signature_md5']
            now = datetime.now()
            now = str(now)[:len(str(now))-7]
            formatted_time = date
            PAYLOAD =b':\x071.111.2\xaa\x01\x02ar\xb2\x01 55ed759fcf94f85813e57b2ec8492f5c\xba\x01\x014\xea\x01@6fb7fdef8658fd03174ed551e82b71b21db8187fa0612c8eaf1b63aa687f1eae\x9a\x06\x014\xa2\x06\x014'
            PAYLOAD = PAYLOAD.replace(b"2023-12-24 04:21:34", str(now).encode()) 
            PAYLOAD = PAYLOAD.replace(b"15f5ba1de5234a2e73cc65b6f34ce4b299db1af616dd1dd8a6f31b147230e5b6", NEW_ACCESS_TOKEN.encode("UTF-8"))
            PAYLOAD = PAYLOAD.replace(b"4666ecda0003f1809655a7a8698573d0", NEW_EXTERNAL_ID.encode("UTF-8"))
            PAYLOAD = PAYLOAD.replace(b"7428b253defc164018c604a1ebbfebdf", SIGNATURE_MD5.encode("UTF-8"))
            PAYLOAD = PAYLOAD.hex()
            PAYLOAD = encrypt_api(PAYLOAD)
            PAYLOAD = bytes.fromhex(PAYLOAD)
            print(f"[INFO] JWT_TOKEN: {JWT_TOKEN}")
            data = GET_LOGIN_DATA(JWT_TOKEN, PAYLOAD, region, proxy)
            print(f"[INFO] Data de login: {data}")
            print(f"[INFO] UID: {uid}, Senha: {password}")
            return {"data":data ,"response" : response_hex , "status_code" : status_code ,"name" : name, "uid" : uid, "password" : password}
        except Exception as e:
            print(f"[ERROR] Erro em GET_PAYLOAD_BY_DATA com proxy {proxy}: {e}")
            return None

def parse_results(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {}
        field_data['wire_type'] = result.wire_type
        if result.wire_type == "varint":
            field_data['data'] = result.data
        if result.wire_type == "string":
            field_data['data'] = result.data
        if result.wire_type == "bytes":
            field_data['data'] = result.data
        elif result.wire_type == 'length_delimited':
            field_data["data"] = parse_results(result.data.results)
        result_dict[result.field] = field_data
    return result_dict

def get_available_room(input_text):
    try:
        parsed_results = Parser().parse(input_text)
        parsed_results_objects = parsed_results
        parsed_results_dict = parse_results(parsed_results_objects)
        json_data = json.dumps(parsed_results_dict)
        return json_data
    except Exception as e:
        print(f"[ERROR] Erro em get_available_room: {e}")
        return None

def GET_LOGIN_DATA(JWT_TOKEN, PAYLOAD, region, proxy=None):
    if region.lower() == "me":
        url = 'https://clientbp.ggblueshark.com/GetLoginData'
    else:
        link = get_region_url(region)
        url = f"{link}GetLoginData"

    headers = {
        'Expect': '100-continue',
        'Authorization': f'Bearer {JWT_TOKEN}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB50',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 10; G011A Build/PI)',
        'Host': 'clientbp.common.ggblueshark.com',
        'Connection': 'close',
        'Accept-Encoding': 'gzip, deflate, br',
    }
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    max_retries = 3
    attempt = 0

    while attempt < max_retries:
        try:
            response = requests.post(url, headers=headers, data=PAYLOAD, proxies=proxies, verify=False, timeout=10)
            response.raise_for_status()    
            x = response.content.hex()
            json_result = get_available_room(x)
            if json_result:
                parsed_data = json.loads(json_result)
                return parsed_data
            else:
                print(f"[ERROR] Falha ao obter json_result de get_available_room (GET_LOGIN_DATA) com proxy {proxy}.")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Request failed in GET_LOGIN_DATA with proxy {proxy}: {e}. Attempt {attempt + 1} of {max_retries}. Retrying...")
            attempt += 1
            time.sleep(2)
    print(f"[ERROR] Falha ao obter dados de login após múltiplas tentativas com proxy {proxy}.")
    return None

def get_fresh_proxy():
    try:
        print("[INFO] Buscando novos proxies da API nekosapi...")
        response = requests.get("https://api.nekolabs.my.id/tools/free-proxy", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        formatted_proxies = []
        if data.get("success") and data.get("result"):
            for p in data["result"]:
                ip = p.get("ip")
                port = p.get("port")
                if ip and port:
                    # API returns http/https status, but for simplicity, we'll assume all are http for now
                    # and let requests handle the scheme based on the target URL.
                    formatted_proxies.append(f"http://{ip}:{port}")
            print(f"[INFO] Proxies encontrados: {formatted_proxies}")
            return formatted_proxies
        else:
            print("[ERROR] API de proxy retornou sucesso=false ou sem resultados.")
            return []
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Erro ao buscar proxies da API: {e}")
        return []

# Função principal de geração de contas, executada em uma thread separada
def account_generation_task():
    target_region = "BR"
    proxy_list = []
    proxy_index = 0
    max_proxy_retries = 5 # How many times to try with different proxies before refreshing the list
    current_proxy_retries = 0

    while True:
        if not proxy_list or current_proxy_retries >= max_proxy_retries:
            proxy_list = get_fresh_proxy()
            proxy_index = 0
            current_proxy_retries = 0
            if not proxy_list:
                print("[CRITICAL] Nenhuma proxy disponível. Aguardando para tentar novamente...")
                time.sleep(60) # Wait a minute before trying to fetch proxies again
                continue

        current_proxy = proxy_list[proxy_index]
        print(f"[INFO] Tentando criar conta para {target_region} com proxy: {current_proxy}")
        
        result = create_acc(target_region, proxy=current_proxy)

        if result:
            account_data = {
                "uid": result.get("uid"),
                "password": result.get("password"),
                "name": result.get("name"),
                "region": target_region,
                "access_token": result.get("data", {}).get("2", {}).get("data"),
                "open_id": result.get("data", {}).get("3", {}).get("data"),
                "created_at": datetime.utcnow()
            }
            try:
                accounts_collection.insert_one(account_data)
                print(f"[SUCCESS] Conta criada e salva no MongoDB: {account_data['uid']}:{account_data['password']}")
                current_proxy_retries = 0 # Reset retry count on success
            except Exception as e:
                print(f"[ERROR] Erro ao salvar conta no MongoDB: {e}")
        else:
            print(f"[FAIL] Falha ao criar conta com proxy {current_proxy}. Tentando próximo proxy...")
            current_proxy_retries += 1

        proxy_index = (proxy_index + 1) % len(proxy_list)
        time.sleep(5) # Delay entre as tentativas para evitar bloqueios

# Rota para verificar a saúde da aplicação
@app.route('/health')
def health_check():
    return jsonify({"status": "online", "message": "Account generator is running"}), 200

if __name__ == "__main__":
    # Inicia a tarefa de geração de contas em uma thread separada
    thread = threading.Thread(target=account_generation_task)
    thread.daemon = True # Permite que a thread seja encerrada quando o programa principal terminar
    thread.start()

    # Inicia o servidor Flask
    # Render usa a variável de ambiente PORT, ou padroniza para 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
