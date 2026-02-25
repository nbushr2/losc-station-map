# Louisiana Weather Station Network

Interactive map and data repository for Louisiana Office of State Climatology (LOSC) weather stations.

## 🗺️ **Live Map**

View the interactive station map: [https://nbushr2.github.io/losc-station-map/](https://nbushr2.github.io/losc-station-map/)

## 📊 **About**

This repository hosts:
- Interactive Leaflet.js map of 150+ Louisiana weather stations
- Historical climate data and observations
- Parish and state boundary GeoJSON files
- Automated data update scripts

## 📁 **Repository Structure**

```
losc-station-map/
├── index.html                    # Interactive map interface
├── data/
│   ├── louisiana_state_boundary.geojson
│   ├── louisiana_parishes.geojson
│   ├── weather_summary_with_coords.csv
│   └── station_list.csv
└── scripts/
    └── weather_summary_with_coordinates.py
```

## 🔄 **Data Updates**

Station data is updated daily via ACIS API. Last update: [Date]

To manually update:
```bash
python scripts/weather_summary_with_coordinates.py
```

## 📥 **Downloads**

- [Station List CSV](./data/station_list.csv)
- [Latest Weather Summary](./data/weather_summary_with_coords.csv)
- [Parish Boundaries GeoJSON](./data/louisiana_parishes.geojson)
- [State Boundary GeoJSON](./data/louisiana_state_boundary.geojson)

## 🛠️ **Technologies**

- **Leaflet.js** - Interactive mapping
- **MarkerCluster** - Station clustering
- **Python** - Data fetching and processing
- **ACIS API** - Climate data source

## 📖 **Data Sources**

- **NOAA ACIS** - Applied Climate Information System
- **NWS COOP** - Cooperative Observer Program
- **LOSC** - Louisiana Office of State Climatology

## 📧 **Contact**

Louisiana Office of State Climatology  
Louisiana State University  
Email: jgrymes@lsu.edu  
Website: https://climate.lsu.edu/

## 📄 **License**

Data provided by NOAA and LOSC. Please cite appropriately when using in publications.

## 🙏 **Citation**

```
Louisiana Office of State Climatology (LOSC). [Year]. Louisiana Weather Station Data. 
Louisiana State University. Retrieved from https://climate.lsu.edu/
```

---

**Maintained by:** Louisiana Office of State Climatology  
**Last Updated:** [Date]
