"""Leaflet map embedded in Streamlit; browser loads pinned public CDN assets."""
import json

def map_html(markers):
    # Escape script delimiters in institutional text before embedding JSON.
    payload = json.dumps(markers, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css">
<style>body{margin:0;font:14px sans-serif}#map{height:600px;border-radius:14px}
.campus-icon{background:white;border:2px solid #007f73;border-radius:12px;box-shadow:0 2px 7px #0003;display:flex;align-items:center;justify-content:center}
.campus-icon img{width:32px;height:32px;object-fit:contain}.fallback{font-size:24px}
</style></head><body><div id="map" role="region" aria-label="Interactive Florida college map"><p>Loading the map… Internet access is needed for map libraries and tiles.</p></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
const schools = """ + payload + """;
if(typeof L !== 'undefined') {
 const map=L.map('map').setView([28.1,-82],6);
 L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{
 attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',maxZoom:19}).addTo(map);
 const group=typeof L.markerClusterGroup==='function' ? L.markerClusterGroup({maxClusterRadius:48,spiderfyOnMaxZoom:true}) : L.layerGroup();
 const positions=[];
 for(const school of schools){
   const content=document.createElement('div');
   if(school.image){const image=document.createElement('img');image.src=school.image;image.alt=school.name;content.appendChild(image);}
   else{content.textContent='🎓';content.className='fallback';}
   const icon=L.divIcon({className:'campus-icon',html:content.innerHTML,iconSize:[40,40],iconAnchor:[20,20]});
   const label=document.createElement('span');label.textContent=school.name;
   L.marker([school.lat,school.lon],{icon,title:school.name,alt:school.name}).bindTooltip(label).bindPopup(school.popup,{maxWidth:320}).addTo(group);
   positions.push([school.lat,school.lon]);
 }
 group.addTo(map);
 if(positions.length)map.fitBounds(positions,{padding:[25,25],maxZoom:10});
} else {document.getElementById('map').textContent='Map libraries could not load. Check your connection. College data is available in the table below.';}
</script></body></html>"""
