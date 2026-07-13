CRIME_BUCKETS = {
    # Violent & Serious Crime
    "violent-crime": "Violent & Serious Crime",
    "possession-of-weapons": "Violent & Serious Crime",
    "robbery": "Violent & Serious Crime",

    # Property & Theft Crime
    "burglary": "Property & Theft Crime",
    "vehicle-crime": "Property & Theft Crime",
    "bicycle-theft": "Property & Theft Crime",
    "shoplifting": "Property & Theft Crime",
    "theft-from-the-person": "Property & Theft Crime",
    "other-theft": "Property & Theft Crime",

    # Quality of Life & Public Order
    "anti-social-behaviour": "Quality of Life & Public Order",
    "public-order": "Quality of Life & Public Order",
    "criminal-damage-arson": "Quality of Life & Public Order",
    "drugs": "Quality of Life & Public Order",

    # Other / Catch-all
    "other-crime": "Other",
    "all-crime": "Other"
}


def process_crime_record(api_record):
    """
    Takes a raw crime record from the police API and appends
    our custom analytical category.
    """
    raw_category = api_record.get("category", "other-crime")

    # Enrich the record with your custom bucket
    api_record["analytical_category"] = CRIME_BUCKETS.get(raw_category, "Other")
    return api_record


# TODO Flatten JSon Crime report into Usable information
# ~~~~~~~~~~
# 18/06/2026 notes for flatterning the crime data json into stats about crime.
# ~~~~~~~~~~
import json
from pathlib import Path

import pandas as pd

# 1. Load your raw API JSON data
# (Replace 'response.json' with your file or direct API response)

# C:\Users\Frede\PycharmProjects\Aqueduct\data\A_raw\police\police_crimes\year=2023\month=06\Barnet.json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
file_path = (
        PROJECT_ROOT
        / "data"
        / "A_raw"
        / "police"
        / "police_crimes"
        / "year=2026"
        / "month=05"
        / "Croydon.json"
)

print(file_path)
print(file_path.exists())
print(PROJECT_ROOT)

with open(file_path, 'r') as f:
    data = json.load(f)
# 2. Flatten the nested JSON structure into a clean dataframe
df = pd.json_normalize(data)

# 3. Export the flattened data directly to a CSV file
df.to_csv('london_crimes_flat.csv', index=False)
print("CSV File successfully created!")

# 4. Count the instances of each crime type
print("\n--- Crime Type Counts ---")
crime_counts = df['category'].value_counts()
print(crime_counts)
# (Optional) Save the aggregated counts to its own CSV
crime_counts.to_csv('crime_type_summary.csv')

outcomes = pd.json_normalize(df["outcome_status"])
outcomes = outcomes.rename(columns={
    "category": "outcome_status.category",
    "date": "outcome_status.date"
})
# --- Your existing code leaves off here ---
df = pd.concat([df.drop(columns=["outcome_status"]), outcomes], axis=1)
df.to_csv('crime_outcomes.csv', index=False)

# =====================================================================
# NEW: Create the Outcome Summary CSV
# =====================================================================

# 1. Fill missing outcomes so active investigations aren't excluded from counts
df['outcome_status.category'] = df['outcome_status.category'].fillna('Under Investigation / No Outcome')

print("\n--- Crime Outcome Counts ---")
# 2. Group, count, and immediately format into a structured DataFrame
outcome_counts = (
    df['outcome_status.category']
    .value_counts()
    .reset_index(name='count')  # Names the summary column 'count'
)

# Print it out to your terminal console so you can see it right away
print(outcome_counts)

# 3. Export the clean aggregated outcome table to its own CSV
outcome_counts.to_csv('outcome_types_summary.csv', index=False)
print("\n✅ 'outcome_types_summary.csv' successfully created!")


# TODO column suggestions

# ons_area, year,
# total_crime_count, lon_avg_total_crime_count, pct_diff_total_crime_count,
# violent_crime_count, pct_diff_violent_crime_count,
# anti_social_behaviour_count, pct_diff_anti_social_behaviour_count,
# theft_count, pct_diff_theft_count,
# burglary_robbery_count, pct_diff_burglary_robbery_count,
# drugs_weapons_count, pct_diff_drugs_weapons_count,
# other_crime_count, pct_diff_other_crime_count,
# resolution_rate, pct_diff_resolution_rate