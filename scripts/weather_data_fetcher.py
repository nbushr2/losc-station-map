#!/usr/bin/env python3
"""
Louisiana Weather Station Data Fetcher
Louisiana Office of State Climatology (LOSC)

Features:
- User-defined date ranges
- Formatted output matching LOSC weekly summaries
- CSV and HTML table generation
- Division summaries (LA01-LA09)
"""

import sys
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

ACIS_URL = 'http://data.rcc-acis.org/MultiStnData'
STATION_FILE = "AgStats_co-op_list_Jay_KBedits1.txt"

# Louisiana Climate Divisions
DIVISIONS = {
    'LA01': 'Northwest',
    'LA02': 'North Central', 
    'LA03': 'Northeast',
    'LA04': 'West Central',
    'LA05': 'Central',
    'LA06': 'East Central',
    'LA07': 'Southwest',
    'LA08': 'South Central',
    'LA09': 'Southeast'
}

# ═══════════════════════════════════════════════════════════════════════════
# STATION LOADER
# ═══════════════════════════════════════════════════════════════════════════

def load_stations(filename):
    """Load station list from text file"""
    stations = {}
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                continue
            
            raw_id = parts[0].strip()
            station_name = parts[1].strip()
            station_id = raw_id[:-2]
            clim_div = "LA" + raw_id[-2:]
            
            stations[station_id] = {
                'name': station_name,
                'division': clim_div
            }
    
    return stations

# ═══════════════════════════════════════════════════════════════════════════
# DATA FETCHER
# ═══════════════════════════════════════════════════════════════════════════

def fetch_station_data(stations, start_date, end_date):
    """
    Fetch weather data from ACIS API
    
    Args:
        stations: dict of station IDs and metadata
        start_date: YYYYMMDD format
        end_date: YYYYMMDD format
    
    Returns:
        dict with station data
    """
    
    station_ids = ",".join(stations.keys())
    
    payload = {
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
    
    print(f"📡 Fetching data from ACIS API...")
    print(f"   Date Range: {start_date} to {end_date}")
    print(f"   Stations: {len(stations)}")
    
    try:
        response = requests.post(
            ACIS_URL,
            data=json.dumps(payload),
            headers={'Content-type': 'application/json'},
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        print(f"✅ Data received successfully!")
        return data
        
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════
# DATA PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════

def fix_missing(val):
    """Convert missing/trace values"""
    if val == "M":
        return np.nan
    if val == "T":
        return 0.0
    try:
        return float(val)
    except:
        return np.nan

def process_data(api_response, stations):
    """Process API response into dataframe"""
    
    station_data = api_response.get('data', [])
    if not station_data:
        print("⚠️ No data returned")
        return pd.DataFrame()
    
    rows = []
    
    for station in station_data:
        meta = station.get("meta", {})
        sids = meta.get("sids", [])
        lookup_id = sids[0].strip() if sids else None
        latlon = meta.get("ll", [None, None])
        
        if lookup_id and lookup_id in stations:
            file_name = stations[lookup_id]['name']
            clim_div = stations[lookup_id]['division']
        else:
            file_name = meta.get("name", "Unknown")
            clim_div = meta.get("climdiv", "Unknown")
        
        api_name = meta.get("name", file_name)
        summary = station.get("smry", [])
        summary += [np.nan] * (17 - len(summary))
        
        # Calculate precipitation departure
        total_p = fix_missing(summary[10])
        normal_p = fix_missing(summary[11])
        pcpn_dfn = total_p - normal_p if not np.isnan(total_p) and not np.isnan(normal_p) else np.nan
        
        # Extract max precip date
        p_max_date = summary[13][1] if isinstance(summary[13], list) and len(summary[13]) > 1 else None
        if p_max_date:
            p_max_date = datetime.strptime(p_max_date, '%Y%m%d').strftime('%m/%d')
        
        # Missing data counts
        missing_tavg = summary[15][1] if isinstance(summary[15], list) and len(summary[15]) > 1 else 0
        missing_totalp = summary[16][1] if isinstance(summary[16], list) and len(summary[16]) > 1 else 0
        
        row = {
            'Station Name': api_name,
            'Station Name (File)': file_name,
            'Climate Division': clim_div,
            'Latitude': latlon[0] if latlon[0] else np.nan,
            'Longitude': latlon[1] if latlon[1] else np.nan,
            'Avg T-Max': fix_missing(summary[0]),
            'Avg T-Min': fix_missing(summary[1]),
            'T-Avg': fix_missing(summary[2]),
            'T-Avg DFN': fix_missing(summary[3]),
            'Highest T-Max': fix_missing(summary[4]),
            'Lowest T-Min': fix_missing(summary[5]),
            'HDD': fix_missing(summary[6]),
            'HDD DFN': fix_missing(summary[7]),
            'CDD': fix_missing(summary[8]),
            'CDD DFN': fix_missing(summary[9]),
            'Total P': total_p,
            'Normal P': normal_p,
            'P-DFN': pcpn_dfn,
            '1-Day Max': fix_missing(summary[12]),
            'P-Max Date': p_max_date,
            'P-Days': fix_missing(summary[14]),
            'Missing T-Avg': missing_tavg,
            'Missing Total P': missing_totalp
        }
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    return df

# ═══════════════════════════════════════════════════════════════════════════
# DIVISION SUMMARIES
# ═══════════════════════════════════════════════════════════════════════════

def calculate_division_summaries(df):
    """Calculate divisional averages like the PDF tables"""
    
    summaries = []
    
    for div_code, div_name in DIVISIONS.items():
        div_data = df[df['Climate Division'] == div_code]
        
        if len(div_data) == 0:
            continue
        
        summary = {
            'Station Name': f'{div_name} Division',
            'Climate Division': div_code,
            'Avg T-Max': div_data['Avg T-Max'].mean(),
            'Avg T-Min': div_data['Avg T-Min'].mean(),
            'T-Avg': div_data['T-Avg'].mean(),
            'T-Avg DFN': div_data['T-Avg DFN'].mean(),
            'Highest T-Max': div_data['Highest T-Max'].max(),
            'Lowest T-Min': div_data['Lowest T-Min'].min(),
            'HDD': div_data['HDD'].mean(),
            'CDD': div_data['CDD'].mean(),
            'Total P': div_data['Total P'].mean(),
            'P-DFN': div_data['P-DFN'].mean(),
            '1-Day Max': div_data['1-Day Max'].max(),
            'P-Days': div_data['P-Days'].max()
        }
        
        summaries.append(summary)
    
    # Statewide summary
    statewide = {
        'Station Name': 'STATE',
        'Climate Division': 'LA',
        'Avg T-Max': df['Avg T-Max'].mean(),
        'Avg T-Min': df['Avg T-Min'].mean(),
        'T-Avg': df['T-Avg'].mean(),
        'T-Avg DFN': df['T-Avg DFN'].mean(),
        'Highest T-Max': df['Highest T-Max'].max(),
        'Lowest T-Min': df['Lowest T-Min'].min(),
        'HDD': df['HDD'].mean(),
        'CDD': df['CDD'].mean(),
        'Total P': df['Total P'].mean(),
        'P-DFN': df['P-DFN'].mean(),
        '1-Day Max': df['1-Day Max'].max(),
        'P-Days': df['P-Days'].max()
    }
    
    summaries.append(statewide)
    
    return pd.DataFrame(summaries)

# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════

def save_csv(df, filename):
    """Save to CSV"""
    df.to_csv(filename, index=False)
    print(f"💾 Saved: {filename}")

def save_html_table(df, filename, title="Station Data"):
    """Save formatted HTML table"""
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #461D7C; }}
        table {{ border-collapse: collapse; width: 100%; font-size: 11px; }}
        th {{ background: #461D7C; color: white; padding: 8px; text-align: center; position: sticky; top: 0; }}
        td {{ border: 1px solid #ddd; padding: 6px; text-align: right; }}
        td:first-child {{ text-align: left; font-weight: 600; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        tr:hover {{ background: #f0f0f0; }}
        .division-row {{ background: #FDD023 !important; font-weight: 700; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {df.to_html(index=False, na_rep='-', float_format='%.1f', classes='data-table')}
</body>
</html>
"""
    
    with open(filename, 'w') as f:
        f.write(html)
    
    print(f"💾 Saved: {filename}")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Louisiana Weather Station Data Fetcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Last 7 days
  python %(prog)s --days 7
  
  # Specific date range
  python %(prog)s --start 20260114 --end 20260120
  
  # Last month
  python %(prog)s --days 30
        """
    )
    
    parser.add_argument('--start', help='Start date (YYYYMMDD)')
    parser.add_argument('--end', help='End date (YYYYMMDD)')
    parser.add_argument('--days', type=int, help='Number of days back from today')
    parser.add_argument('--station-file', default=STATION_FILE, help='Station list file')
    parser.add_argument('--output', default='weather_summary', help='Output filename prefix')
    
    args = parser.parse_args()
    
    # Determine date range
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    elif args.days:
        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y%m%d')
    else:
        # Default: last 7 days
        end_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
    
    print("=" * 70)
    print("Louisiana Office of State Climatology - Data Fetcher")
    print("=" * 70)
    
    # Load stations
    print(f"📋 Loading stations from: {args.station_file}")
    stations = load_stations(args.station_file)
    print(f"   Found {len(stations)} stations")
    
    # Fetch data
    api_response = fetch_station_data(stations, start_date, end_date)
    
    # Process data
    print("⚙️  Processing data...")
    df = process_data(api_response, stations)
    
    if df.empty:
        print("❌ No data to process")
        return
    
    print(f"   Processed {len(df)} stations")
    
    # Calculate division summaries
    print("📊 Calculating division summaries...")
    div_summary = calculate_division_summaries(df)
    
    # Save outputs
    print("\n💾 Saving outputs...")
    
    # Full station data
    save_csv(df, f"{args.output}_stations.csv")
    save_html_table(df, f"{args.output}_stations.html", 
                    f"Station Data: {start_date} to {end_date}")
    
    # Division summaries
    save_csv(div_summary, f"{args.output}_divisions.csv")
    save_html_table(div_summary, f"{args.output}_divisions.html",
                    f"Division Summaries: {start_date} to {end_date}")
    
    print("\n✅ Complete!")
    print(f"   Date Range: {start_date} - {end_date}")
    print(f"   Stations: {len(df)}")
    print(f"   Divisions: {len(div_summary) - 1}")  # -1 for STATE row

if __name__ == "__main__":
    main()
