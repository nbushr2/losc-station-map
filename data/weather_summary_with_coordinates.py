
import sys, json, requests, pandas as pd, numpy as np

# --- Configuration ---
state = "LA"
start_date = "20250507"
end_date = "20250508"
station_file = "AgStats_co-op_list_Jay_KBedits1.txt"

station_dict = {}
requested_ids = []

with open(station_file, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            continue
        raw_id = parts[0].strip()
        file_station_name = parts[1].strip()
        station_id = raw_id[:-2]
        clim_div = "LA" + raw_id[-2:]
        station_dict[station_id] = (file_station_name, clim_div)
        requested_ids.append(station_id)

station_ids = ",".join(requested_ids)

input_dict = {
    "sids": station_ids,
    "sdate": start_date,
    "edate": end_date,
    "meta": ["name", "climdiv", "sids", "ll"],
    "elems": [
        {"name": "maxt", "interval": "dly", "smry": "mean", "smry_only": 1},
        {"name": "mint", "interval": "dly", "smry": "mean", "smry_only": 1},
        {"name": "avgt", "interval": "dly", "smry": "mean", "smry_only": 1},
        {"name": "avgt", "interval": "dly", "smry": "mean", "smry_only": 1, "normal": "departure"},
        {"name": "maxt", "interval": "dly", "smry": "max", "smry_only": 1},
        {"name": "mint", "interval": "dly", "smry": "min", "smry_only": 1},
        {"name": "hdd",  "interval": "dly", "smry": "sum", "smry_only": 1},
        {"name": "hdd",  "interval": "dly", "smry": "sum", "smry_only": 1, "normal": "departure"},
        {"name": "cdd",  "interval": "dly", "smry": "sum", "smry_only": 1},
        {"name": "cdd",  "interval": "dly", "smry": "sum", "smry_only": 1, "normal": "departure"},
        {"name": "pcpn", "interval": "dly", "smry": "sum", "smry_only": 1},
        {"name": "pcpn", "interval": "dly", "smry": "sum", "smry_only": 1, "normal": "1"},
        {"name": "pcpn", "interval": "dly", "smry": "max", "smry_only": 1},
        {"name": "pcpn", "interval": "dly", "smry": {"reduce": "max", "add": "date"}, "smry_only": 1},
        {"name": "pcpn", "interval": "dly", "smry": "cnt_ge_0.01", "duration": "dly", "smry_only": 1},
        {"name": "avgt", "interval": "dly", "smry": {"reduce": "mean", "add": "mcnt"}, "smry_only": 1},
        {"name": "pcpn", "interval": "dly", "smry": {"reduce": "sum",  "add": "mcnt"}, "smry_only": 1}
    ]
}

url = 'http://data.rcc-acis.org/MultiStnData'
try:
    response = requests.post(url, data=json.dumps(input_dict),
                             headers={'Content-type': 'application/json'}, timeout=40)
    response.raise_for_status()
    data_response = response.json()
except Exception as e:
    sys.exit(f"Error fetching data: {e}")

stations_data = data_response.get('data', [])
if not stations_data:
    sys.exit("No station data returned by the API.")

out_columns = [
    "Station Name", "Station Name (File)", "Climate Division", "Latitude", "Longitude",
    "Avg T-Max", "Avg T-Min", "T-Avg", "T-Avg DFN", "Highest T-Max", "Lowest T-Min", "HDD", "HDD DFN",
    "CDD", "CDD DFN", "Total P", "Normal P", "P-DFN", "1-Day Max", "P-Max Date", "P-Days",
    "Missing T-Avg", "Missing Total P"
]

weather_data = []

def fix_missing(val):
    if val == "M":
        return -999
    if val == "T":
        return 0
    try:
        return float(val)
    except Exception:
        return val

for station in stations_data:
    meta = station.get("meta", {})
    sids = meta.get("sids", [])
    lookup_id = sids[0].strip() if sids else None
    latlon = meta.get("ll", [None, None])

    if lookup_id and lookup_id in station_dict:
        file_station_name, clim_div = station_dict[lookup_id]
    else:
        file_station_name = meta.get("name", "Unknown Station")
        clim_div = meta.get("climdiv", "Unknown Division")
    
    api_station_name = meta.get("name", file_station_name)
    summary = station.get("smry", [])
    summary += [np.nan] * (17 - len(summary))

    pcpn_dfn = fix_missing(summary[10]) - fix_missing(summary[11])
    p_max_date = summary[13][1] if isinstance(summary[13], list) and len(summary[13]) > 1 else "N/A"
    missing_tavg = summary[15][1] if isinstance(summary[15], list) and len(summary[15]) > 1 else np.nan
    missing_totalp = summary[16][1] if isinstance(summary[16], list) and len(summary[16]) > 1 else np.nan

    row = [
        api_station_name, file_station_name, clim_div, latlon[0], latlon[1],
        fix_missing(summary[0]), fix_missing(summary[1]), fix_missing(summary[2]),
        fix_missing(summary[3]), fix_missing(summary[4]), fix_missing(summary[5]),
        fix_missing(summary[6]), fix_missing(summary[7]), fix_missing(summary[8]),
        fix_missing(summary[9]), fix_missing(summary[10]), fix_missing(summary[11]),
        pcpn_dfn, fix_missing(summary[12]), p_max_date, fix_missing(summary[14]),
        missing_tavg, missing_totalp
    ]
    weather_data.append(row)

df = pd.DataFrame(weather_data, columns=out_columns)
df.to_csv("weather_summary_with_coords.csv", index=False)
print("File 'weather_summary_with_coords.csv' has been created.")
