#!/usr/bin/env python3
"""
Louisiana Weather Station Tables Generator
==========================================

Generates station data tables with divisional summaries matching the weekly newsletter format.

Usage:
    python generate_tables.py --start 20260114 --end 20260120
    python generate_tables.py --days 7
    python generate_tables.py --start 20260101 --end 20260131 --output january_report.xlsx

Features:
- Fetches data from ACIS API
- Calculates divisional summaries
- Calculates statewide summary
- Exports to Excel with formatting
- Exports to CSV
- Exports to HTML

Author: Louisiana Office of State Climatology
"""

import sys
import json
import requests
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════

ACIS_URL = 'https://data.rcc-acis.org/MultiStnData'
STATION_LIST = 'AgStats_co-op_list_Jay_KBedits1.txt'

DIVISION_NAMES = {
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

# ═══════════════════════════════════════════════════════════════
#  COMMAND LINE ARGUMENTS
# ═══════════════════════════════════════════════════════════════

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate Louisiana weather station tables',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --days 7                    # Last 7 days
  %(prog)s --start 20260114 --end 20260120
  %(prog)s --start 20260101 --end 20260131 --output jan2026.xlsx
  %(prog)s --days 30 --format csv      # CSV format
        """
    )
    
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument('--start', help='Start date (YYYYMMDD)')
    date_group.add_argument('--days', type=int, help='Number of days back from yesterday')
    
    parser.add_argument('--end', help='End date (YYYYMMDD), required if --start used')
    parser.add_argument('--output', '-o', default='weather_summary.xlsx', 
                       help='Output filename (default: weather_summary.xlsx)')
    parser.add_argument('--format', '-f', choices=['excel', 'csv', 'html', 'all'], 
                       default='excel', help='Output format (default: excel)')
    parser.add_argument('--station-file', default=STATION_LIST,
                       help=f'Station list file (default: {STATION_LIST})')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Validate date arguments
    if args.start and not args.end:
        parser.error('--end is required when --start is specified')
    
    if args.days:
        # Calculate dates
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=args.days - 1)
        args.start = start_date.strftime('%Y%m%d')
        args.end = end_date.strftime('%Y%m%d')
    
    return args

# ═══════════════════════════════════════════════════════════════
#  LOAD STATION LIST
# ═══════════════════════════════════════════════════════════════

def load_station_list(station_file):
    """Load station list from file"""
    station_dict = {}
    requested_ids = []
    
    try:
        with open(station_file, 'r') as f:
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
                clim_div = 'LA' + raw_id[-2:]
                
                station_dict[station_id] = (file_station_name, clim_div)
                requested_ids.append(station_id)
    
    except FileNotFoundError:
        print(f"ERROR: Station file '{station_file}' not found")
        sys.exit(1)
    
    return station_dict, requested_ids

# ═══════════════════════════════════════════════════════════════
#  FETCH DATA FROM ACIS API
# ═══════════════════════════════════════════════════════════════

def fetch_acis_data(requested_ids, start_date, end_date, verbose=False):
    """Fetch data from ACIS API"""
    station_ids = ','.join(requested_ids)
    
    input_dict = {
        'sids': station_ids,
        'sdate': start_date,
        'edate': end_date,
        'meta': ['name', 'climdiv', 'sids'],
        'elems': [
            {'name': 'maxt', 'interval': 'dly', 'smry': 'mean', 'smry_only': 1},
            {'name': 'mint', 'interval': 'dly', 'smry': 'mean', 'smry_only': 1},
            {'name': 'avgt', 'interval': 'dly', 'smry': 'mean', 'smry_only': 1},
            {'name': 'avgt', 'interval': 'dly', 'smry': 'mean', 'smry_only': 1, 'normal': 'departure'},
            {'name': 'maxt', 'interval': 'dly', 'smry': 'max', 'smry_only': 1},
            {'name': 'mint', 'interval': 'dly', 'smry': 'min', 'smry_only': 1},
            {'name': 'hdd', 'interval': 'dly', 'smry': 'sum', 'smry_only': 1},
            {'name': 'hdd', 'interval': 'dly', 'smry': 'sum', 'smry_only': 1, 'normal': 'departure'},
            {'name': 'cdd', 'interval': 'dly', 'smry': 'sum', 'smry_only': 1},
            {'name': 'cdd', 'interval': 'dly', 'smry': 'sum', 'smry_only': 1, 'normal': 'departure'},
            {'name': 'pcpn', 'interval': 'dly', 'smry': 'sum', 'smry_only': 1},
            {'name': 'pcpn', 'interval': 'dly', 'smry': 'sum', 'smry_only': 1, 'normal': '1'},
            {'name': 'pcpn', 'interval': 'dly', 'smry': 'max', 'smry_only': 1},
            {'name': 'pcpn', 'interval': 'dly', 'smry': {'reduce': 'max', 'add': 'date'}, 'smry_only': 1},
            {'name': 'pcpn', 'interval': 'dly', 'smry': 'cnt_ge_0.01', 'duration': 'dly', 'smry_only': 1},
            {'name': 'avgt', 'interval': 'dly', 'smry': {'reduce': 'mean', 'add': 'mcnt'}, 'smry_only': 1},
            {'name': 'pcpn', 'interval': 'dly', 'smry': {'reduce': 'sum', 'add': 'mcnt'}, 'smry_only': 1}
        ]
    }
    
    if verbose:
        print(f"Fetching data from ACIS API...")
        print(f"  Stations: {len(requested_ids)}")
        print(f"  Date range: {start_date} to {end_date}")
    
    try:
        response = requests.post(
            ACIS_URL,
            data=json.dumps(input_dict),
            headers={'Content-type': 'application/json'},
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        
        stations_data = data.get('data', [])
        if not stations_data:
            print("ERROR: No station data returned by the API")
            sys.exit(1)
        
        if verbose:
            print(f"  ✓ Received data for {len(stations_data)} stations")
        
        return stations_data
    
    except requests.exceptions.Timeout:
        print("ERROR: ACIS API request timed out")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch data from ACIS API: {e}")
        sys.exit(1)

# ═══════════════════════════════════════════════════════════════
#  PROCESS STATION DATA
# ═══════════════════════════════════════════════════════════════

def process_station_data(stations_data, station_dict, verbose=False):
    """Process raw ACIS data into DataFrame"""
    
    def fix_missing(val):
        """Convert missing values"""
        if val == 'M':
            return -999
        if val == 'T':
            return 0
        try:
            return float(val)
        except:
            return val
    
    out_columns = [
        'Station Name', 'Station Name (File)', 'Climate Division',
        'Avg T-Max', 'Avg T-Min', 'T-Avg', 'T-Avg DFN',
        'Highest T-Max', 'Lowest T-Min',
        'HDD', 'HDD DFN', 'HDD Normal', 'Percent of Normal HDD',
        'CDD', 'CDD DFN', 'CDD Normal', 'Percent of Normal CDD',
        'Total P', 'Normal P', 'P-DFN',
        '1-Day Max', 'P-Max Date', 'P-Days',
        'Missing T-Avg', 'Missing Total P'
    ]
    
    weather_data = []
    
    for station in stations_data:
        meta = station.get('meta', {})
        sid = meta.get('sids', [None])[0]
        if sid:
            sid = sid.strip()
        
        file_name, div = station_dict.get(sid, (meta.get('name', 'Unknown'), meta.get('climdiv', 'Unknown')))
        name = meta.get('name', file_name)
        
        smry = station.get('smry', [])
        if len(smry) < 17:
            smry += [np.nan] * (17 - len(smry))
        
        # Extract values
        atx = fix_missing(smry[0])
        atn = fix_missing(smry[1])
        tav = fix_missing(smry[2])
        tdfn = fix_missing(smry[3])
        htx = fix_missing(smry[4])
        ltn = fix_missing(smry[5])
        
        # HDD
        hdd = fix_missing(smry[6])
        hdd_dfn = fix_missing(smry[7])
        hdd_norm = np.nan if (hdd == -999 or hdd_dfn == -999) else hdd - hdd_dfn
        pct_hdd = '-' if pd.isna(hdd_norm) or hdd_norm == 0 else hdd / hdd_norm * 100
        
        # CDD
        cdd = fix_missing(smry[8])
        cdd_dfn = fix_missing(smry[9])
        cdd_norm = np.nan if (cdd == -999 or cdd_dfn == -999) else cdd - cdd_dfn
        pct_cdd = '-' if pd.isna(cdd_norm) or cdd_norm == 0 else cdd / cdd_norm * 100
        
        # Precipitation
        total_p = fix_missing(smry[10])
        normal_p = fix_missing(smry[11])
        p_diff = np.nan if (total_p == -999 or normal_p == -999) else total_p - normal_p
        
        od = fix_missing(smry[12])
        md = smry[13]
        pdate = md[1] if isinstance(md, list) and len(md) > 1 else 'N/A'
        pdays = fix_missing(smry[14])
        
        # Missing counts
        tmc = smry[15]
        miss_t = tmc[1] if isinstance(tmc, list) and len(tmc) > 1 else np.nan
        pmc = smry[16]
        miss_p = pmc[1] if isinstance(pmc, list) and len(pmc) > 1 else np.nan
        
        weather_data.append([
            name, file_name, div,
            atx, atn, tav, tdfn, htx, ltn,
            hdd, hdd_dfn, hdd_norm, pct_hdd,
            cdd, cdd_dfn, cdd_norm, pct_cdd,
            total_p, normal_p, p_diff,
            od, pdate, pdays,
            miss_t, miss_p
        ])
    
    df = pd.DataFrame(weather_data, columns=out_columns)
    
    # Convert numeric columns
    numeric_cols = [
        'Avg T-Max', 'Avg T-Min', 'T-Avg', 'T-Avg DFN',
        'Highest T-Max', 'Lowest T-Min', 'HDD', 'HDD DFN', 'HDD Normal',
        'CDD', 'CDD DFN', 'CDD Normal', 'Total P', 'Normal P', 'P-DFN',
        '1-Day Max', 'P-Days', 'Missing T-Avg', 'Missing Total P'
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df['P-Max Date'] = pd.to_datetime(df['P-Max Date'], errors='coerce')
    
    if verbose:
        print(f"  ✓ Processed {len(df)} stations")
    
    return df

# ═══════════════════════════════════════════════════════════════
#  CALCULATE SUMMARIES
# ═══════════════════════════════════════════════════════════════

def create_divisional_summaries(df, verbose=False):
    """Calculate divisional summary rows"""
    
    def create_div_summary(group):
        """Calculate summary for one division"""
        gd = group.replace(-999, np.nan)
        
        avg_hdd = gd['HDD'].mean()
        avg_hdd_norm = gd['HDD Normal'].mean()
        pct_hdd = (avg_hdd / avg_hdd_norm * 100) if pd.notna(avg_hdd_norm) and avg_hdd_norm != 0 else np.nan
        
        avg_cdd = gd['CDD'].mean()
        avg_cdd_norm = gd['CDD Normal'].mean()
        pct_cdd = (avg_cdd / avg_cdd_norm * 100) if pd.notna(avg_cdd_norm) and avg_cdd_norm != 0 else np.nan
        
        return pd.Series({
            'Station Name': 'Divisional Summary',
            'Station Name (File)': '',
            'Climate Division': group['Climate Division'].iloc[0],
            'Avg T-Max': gd['Avg T-Max'].mean(),
            'Avg T-Min': gd['Avg T-Min'].mean(),
            'T-Avg': gd['T-Avg'].mean(),
            'T-Avg DFN': gd['T-Avg DFN'].mean(),
            'Highest T-Max': gd['Highest T-Max'].max(),
            'Lowest T-Min': gd['Lowest T-Min'].min(),
            'HDD': avg_hdd,
            'HDD DFN': gd['HDD DFN'].mean(),
            'HDD Normal': avg_hdd_norm,
            'Percent of Normal HDD': pct_hdd,
            'CDD': avg_cdd,
            'CDD DFN': gd['CDD DFN'].mean(),
            'CDD Normal': avg_cdd_norm,
            'Percent of Normal CDD': pct_cdd,
            'Total P': gd['Total P'].mean(),
            'Normal P': gd['Normal P'].mean(),
            'P-DFN': gd['P-DFN'].mean(),
            '1-Day Max': gd['1-Day Max'].max(),
            'P-Max Date': '',
            'P-Days': gd['P-Days'].max(),
            'Missing T-Avg': '',
            'Missing Total P': ''
        })
    
    # Create summary for each division
    divisions = df.groupby('Climate Division', sort=True)
    final_list = []
    
    for div_code, group in divisions:
        final_list.append(group)
        final_list.append(pd.DataFrame([create_div_summary(group)]))
    
    df_final = pd.concat(final_list, ignore_index=True)
    
    if verbose:
        print(f"  ✓ Created summaries for {len(divisions)} divisions")
    
    return df_final

def create_state_summary(df_div):
    """Calculate statewide summary"""
    gd = df_div.replace(-999, np.nan)
    
    avg_hdd = gd['HDD'].mean()
    avg_hdd_norm = gd['HDD Normal'].mean()
    pct_hdd = (avg_hdd / avg_hdd_norm * 100) if pd.notna(avg_hdd_norm) and avg_hdd_norm != 0 else np.nan
    
    avg_cdd = gd['CDD'].mean()
    avg_cdd_norm = gd['CDD Normal'].mean()
    pct_cdd = (avg_cdd / avg_cdd_norm * 100) if pd.notna(avg_cdd_norm) and avg_cdd_norm != 0 else np.nan
    
    return pd.Series({
        'Station Name': 'State',
        'Climate Division': '',
        'Division Name': 'State',
        'Avg T-Max': gd['Avg T-Max'].mean(),
        'Avg T-Min': gd['Avg T-Min'].mean(),
        'T-Avg': gd['T-Avg'].mean(),
        'T-Avg DFN': gd['T-Avg DFN'].mean(),
        'Highest T-Max': gd['Highest T-Max'].max(),
        'Lowest T-Min': gd['Lowest T-Min'].min(),
        'HDD': avg_hdd,
        'HDD DFN': gd['HDD DFN'].mean(),
        'HDD Normal': avg_hdd_norm,
        'Percent of Normal HDD': pct_hdd,
        'CDD': avg_cdd,
        'CDD DFN': gd['CDD DFN'].mean(),
        'CDD Normal': avg_cdd_norm,
        'Percent of Normal CDD': pct_cdd,
        'Total P': gd['Total P'].mean(),
        'Normal P': gd['Normal P'].mean(),
        'P-DFN': gd['P-DFN'].mean(),
        '1-Day Max': gd['1-Day Max'].max(),
        'P-Max Date': '',
        'P-Days': gd['P-Days'].max()
    })

# ═══════════════════════════════════════════════════════════════
#  EXPORT FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def export_to_excel(df_final, output_file, verbose=False):
    """Export to Excel with formatting"""
    
    # Create division summaries sheet
    df_div = df_final[df_final['Station Name'] == 'Divisional Summary'].copy()
    df_div.insert(2, 'Division Name', df_div['Climate Division'].map(DIVISION_NAMES).fillna('Unknown'))
    df_div = pd.concat([df_div, pd.DataFrame([create_state_summary(df_div)])], ignore_index=True)
    
    # Clean up for display
    _df = df_final.replace(-999, '-').copy()
    _df_div = df_div.replace(-999, '-').copy()
    
    _df['Station Name'] = _df['Station Name'].replace('Divisional Summary', 'Division')
    _df.rename(columns={'Station Name': 'Stations'}, inplace=True)
    
    _df_div['Station Name'] = _df_div['Station Name'].replace('Divisional Summary', 'Division')
    _df_div.drop(columns=['Station Name', 'P-Max Date', 'Missing T-Avg', 'Missing Total P'], inplace=True)
    _df_div.rename(columns={'Division Name': 'Divisions'}, inplace=True)
    
    # Replace NaN with None
    _df = _df.where(pd.notnull(_df), None)
    _df_div = _df_div.where(pd.notnull(_df_div), None)
    
    # Write to Excel
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        _df.to_excel(writer, sheet_name='Summary', index=False)
        _df_div.to_excel(writer, sheet_name='Division Summaries', index=False)
        
        # Format Summary sheet
        wb = writer.book
        ws = writer.sheets['Summary']
        
        # Formats
        fmt_center = wb.add_format({'align': 'center'})
        fmt_1dec = wb.add_format({'num_format': '0.0', 'align': 'center'})
        fmt_2dec = wb.add_format({'num_format': '0.00', 'align': 'center'})
        fmt_int = wb.add_format({'num_format': '0', 'align': 'center'})
        fmt_bold = wb.add_format({'bold': True, 'align': 'center'})
        
        # Set column widths
        ws.set_column('A:A', 20)
        ws.set_column('B:Y', 12, fmt_center)
        
        # Bold header
        for col_num, value in enumerate(_df.columns.values):
            ws.write(0, col_num, value, fmt_bold)
    
    if verbose:
        print(f"  ✓ Exported to Excel: {output_file}")

def export_to_csv(df_final, output_file, verbose=False):
    """Export to CSV"""
    base_name = output_file.rsplit('.', 1)[0]
    
    # Stations CSV
    stations_file = f"{base_name}_stations.csv"
    df_final.to_csv(stations_file, index=False)
    
    # Divisions CSV
    df_div = df_final[df_final['Station Name'] == 'Divisional Summary'].copy()
    divisions_file = f"{base_name}_divisions.csv"
    df_div.to_csv(divisions_file, index=False)
    
    if verbose:
        print(f"  ✓ Exported to CSV:")
        print(f"    - {stations_file}")
        print(f"    - {divisions_file}")

def export_to_html(df_final, output_file, verbose=False):
    """Export to HTML"""
    base_name = output_file.rsplit('.', 1)[0]
    html_file = f"{base_name}.html"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Louisiana Weather Data</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #461D7C; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th {{ background: #461D7C; color: white; padding: 10px; text-align: left; }}
            td {{ border: 1px solid #ddd; padding: 8px; }}
            tr:nth-child(even) {{ background: #f2f2f2; }}
            .summary-row {{ background: #e8f0fe; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>Louisiana Weather Station Data</h1>
        {df_final.to_html(index=False, classes='data')}
    </body>
    </html>
    """
    
    with open(html_file, 'w') as f:
        f.write(html)
    
    if verbose:
        print(f"  ✓ Exported to HTML: {html_file}")

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    """Main execution"""
    args = parse_arguments()
    
    print("=" * 60)
    print("Louisiana Weather Station Tables Generator")
    print("=" * 60)
    print(f"Date range: {args.start} to {args.end}")
    print(f"Output: {args.output}")
    print(f"Format: {args.format}")
    print("=" * 60)
    print()
    
    # Load station list
    print("📂 Loading station list...")
    station_dict, requested_ids = load_station_list(args.station_file)
    print(f"  ✓ Loaded {len(requested_ids)} stations")
    print()
    
    # Fetch data
    print("🌐 Fetching data from ACIS API...")
    stations_data = fetch_acis_data(requested_ids, args.start, args.end, args.verbose)
    print()
    
    # Process data
    print("⚙️  Processing station data...")
    df = process_station_data(stations_data, station_dict, args.verbose)
    print()
    
    # Create summaries
    print("📊 Calculating divisional summaries...")
    df_final = create_divisional_summaries(df, args.verbose)
    print()
    
    # Export
    print("💾 Exporting data...")
    if args.format == 'excel' or args.format == 'all':
        export_to_excel(df_final, args.output, args.verbose)
    
    if args.format == 'csv' or args.format == 'all':
        export_to_csv(df_final, args.output, args.verbose)
    
    if args.format == 'html' or args.format == 'all':
        export_to_html(df_final, args.output, args.verbose)
    
    print()
    print("=" * 60)
    print("✅ COMPLETE!")
    print("=" * 60)

if __name__ == '__main__':
    main()
