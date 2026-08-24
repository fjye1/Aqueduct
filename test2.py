import pandas as pd

# LONDON_BOROUGH_NAMES_UK = [
#     "City of London", "Barking and Dagenham", "Barnet", "Bexley", "Brent",
#     "Bromley", "Camden", "Croydon", "Ealing", "Enfield",
#     "Greenwich", "Hackney", "Hammersmith and Fulham", "Haringey", "Harrow",
#     "Havering", "Hillingdon", "Hounslow", "Islington", "Kensington and Chelsea",
#     "Kingston upon Thames", "Lambeth", "Lewisham", "Merton", "Newham",
#     "Redbridge", "Richmond upon Thames", "Southwark", "Sutton", "Tower Hamlets",
#     "Waltham Forest", "Wandsworth", "Westminster"
# ]
#
# df = pd.read_csv("data/PCD_OA21_LSOA21_MSOA21_LAD_MAY26_UK_LU.csv")
#
# print(df.shape)
# print(df.head)
#
# df = df.drop(df[~df['ladnm'].isin(LONDON_BOROUGH_NAMES_UK)].index)
# print(df.shape)
# print(df.head)
#
#
# df =df.drop_duplicates(subset=['oa21cd'])
#
# print(df.shape)
# print(df.head)

# df.to_csv("OA-LAD.csv")

df = pd.read_csv('OA-LAD.csv')

# Drop the unnamed column at index position 0 along with your other columns
cols_to_drop = [ "lsoa21nm", "msoa21nm", "ladnmw"]

df = df.drop(columns=cols_to_drop)

print(df.shape)
print(df.head)

df.to_csv("OA-LAD.csv")

# import csv
# import json
# import os
# import re
#
# # File path to your downloaded ONS/NSPL postcode lookup CSV
# CSV_FILE = 'postcode_to_oa.csv'
# OUTPUT_DIR = './postcode_chunks'
#
# os.makedirs(OUTPUT_DIR, exist_ok=True)
#
# chunks = {}
#
# with open(CSV_FILE, mode='r', encoding='utf-8-sig') as f:
#     reader = csv.DictReader(f)
#     for row in reader:
#         # Clean postcode (remove spaces, uppercase)
#         raw_postcode = row['postcode']  # Replace with your CSV header name
#         cleaned_pc = re.sub(r'\s+', '', raw_postcode).upper()
#         oa_code = row['oa_code']  # Replace with your CSV header name
#
#         # Outward code (e.g., 'LU61AT' -> outcode is everything before last 3 chars)
#         if len(cleaned_pc) > 3:
#             outcode = cleaned_pc[:-3]
#         else:
#             continue
#
#         if outcode not in chunks:
#             chunks[outcode] = {}
#
#         chunks[outcode][cleaned_pc] = oa_code
#
# # Save into individual JSON files
# for outcode, data in chunks.items():
#     with open(os.path.join(OUTPUT_DIR, f"{outcode}.json"), 'w') as out_f:
#         json.dump(data, out_f, separators=(',', ':'))
#
# print(f"Created {len(chunks)} prefix chunks in {OUTPUT_DIR}")
#
# / **
# *Standalone
# Postcode - to - OA
# Lookup
# Function
# * @ param
# {string}
# userPostcode - e.g.
# "LU6 1AT" or "lu61at"
# * @ param
# {string}
# baseUrl - Directory
# where
# JSON
# files
# are
# hosted
# * @ returns
# {Promise < string | null >}
# Returns
# the
# OA
# code or null if not found
# * /
# async function
# lookupOAFromPostcode(userPostcode, baseUrl='/data/postcodes')
# {
# // 1.
# Sanitize
# input: remove
# spaces and convert
# to
# uppercase
# const
# cleanPostcode = userPostcode.replace( /\s + / g, '').toUpperCase();
#
# // Basic
# UK
# postcode
# validation
# check
# length(5
# to
# 7
# characters)
# if (cleanPostcode.length < 5 | | cleanPostcode.length > 7) {
# throw new Error("Invalid postcode length");
# }
#
# // 2. Extract outward code (everything except the
# last
# 3
# characters)
# const
# outcode = cleanPostcode.slice(0, -3);
#
# try {
# // 3. Fetch only the tiny JSON file for this outward code (~10KB)
# const response = await fetch(`${baseUrl} / ${outcode}.json`, {
# cache: "force-cache" // Allows
# browser / CDN
# to
# cache
# repeat
# requests
# });
#
# if (!response.ok) {
# return null; // Outward
# code
# chunk
# not found
# }
#
# const
# chunkData = await response.json();
#
# // 4.
# Return
# the
# OA
# area
# code
# mapped
# to
# this
# specific
# postcode
# const
# oaCode = chunkData[cleanPostcode] | | null;
# return oaCode;
#
# } catch(err)
# {
# console.error("Lookup failed:", err);
# return null;
# }
# }
#
# // --- Example
# Usage
# on
# Website - --
# async function
# handleSearch(inputPostcode)
# {
#     const
# oaCode = await lookupOAFromPostcode(inputPostcode);
#
# if (oaCode)
# {
# // Redirect or load
# data
# page
# for that Output Area
# window.location.href = ` / area /${oaCode}
# `;
# } else {
# alert("Postcode not found. Please check and try again.");
# }
# }