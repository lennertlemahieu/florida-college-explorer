"""Leaflet map embedded in Streamlit; browser loads pinned public CDN assets."""
import json

def map_html(markers):
    # Escape script delimiters in institutional text before embedding JSON.
    payload = json.dumps(markers, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<style>
body{margin:0;font:14px sans-serif}
#map{height:100vh;border-radius:16px;background:#102e3c}
.leaflet-top .leaflet-control{margin-top:14px}
.leaflet-left .leaflet-control{margin-left:14px}
.leaflet-right .leaflet-control{margin-right:14px}
.leaflet-touch .leaflet-bar,.leaflet-touch .leaflet-control-layers{border:1px solid #c9ddd5;border-radius:9px;box-shadow:0 3px 12px #031b2a55}
.leaflet-bar a:first-child{border-radius:8px 8px 0 0}
.leaflet-bar a:last-child{border-radius:0 0 8px 8px}
.campus-icon,.campus-cluster{display:grid;place-items:center;box-sizing:border-box;box-shadow:0 3px 12px #031b2ad9}
.campus-icon{background:#fff;border:2px solid #d0f8ef;border-radius:50%}
.campus-icon-dark{background:#123440}
.campus-icon::after{content:'';position:absolute;bottom:-4px;left:calc(50% - 4px);width:8px;height:8px;background:#d0f8ef;transform:rotate(45deg);z-index:-1}
.campus-icon .campus-image{width:27px;height:27px;display:grid;place-items:center;overflow:hidden}
.leaflet-container .leaflet-marker-pane .campus-image img{display:block;width:27px;height:27px;object-fit:contain}
.fallback{font-size:19px}
.campus-cluster{background:#123c48;color:#fff;border:2px solid #b5fff0;border-radius:50%;font:bold 13px sans-serif}
.leaflet-tooltip{background:#123440;color:white;border-color:#315463;border-radius:6px}
.leaflet-tooltip-top::before{border-top-color:#315463}
</style></head><body><div id="map" role="region" aria-label="Interactive Florida college map"><p>Loading the map… Internet access is needed for map libraries and tiles.</p></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
const schools = """ + payload + """;
if(typeof L !== 'undefined') {
 const map=L.map('map',{zoomSnap:0.25,scrollWheelZoom:false});
 const imagery=L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{
   attribution:'Imagery &copy; <a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9">Esri, Vantor, Earthstar Geographics, and the GIS User Community</a>',
   maxNativeZoom:19,maxZoom:20
 }).addTo(map);
 const streets=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
   attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
   maxNativeZoom:19,maxZoom:20
 });
 L.control.layers({'Aerial imagery':imagery,'Street map':streets}).addTo(map);
 const group=typeof L.markerClusterGroup==='function' ? L.markerClusterGroup({
   maxClusterRadius:36,
   showCoverageOnHover:false,
   spiderfyOnMaxZoom:true,
   iconCreateFunction:cluster=>L.divIcon({className:'campus-cluster',html:String(cluster.getChildCount()),iconSize:[34,34]})
 }) : L.layerGroup();
 const positions=[];
 for(const school of schools){
   const content=document.createElement('div');
   if(school.image){
     content.className='campus-image';
     const image=document.createElement('img');
     image.src=school.image;
     image.alt=school.name;
     content.appendChild(image);
   }
   else{content.textContent='🎓';content.className='fallback';}
   const iconClass=school.darkBackground ? 'campus-icon campus-icon-dark' : 'campus-icon';
   const icon=L.divIcon({className:iconClass,html:content,iconSize:[36,36],iconAnchor:[18,39],tooltipAnchor:[0,-38],popupAnchor:[0,-34]});
   const label=document.createElement('span');label.textContent=school.name;
   L.marker([school.lat,school.lon],{icon,title:school.name,alt:school.name}).bindTooltip(label).bindPopup(school.popup,{maxWidth:320}).addTo(group);
   positions.push([school.lat,school.lon]);
 }
 const floridaBounds=[[24.4,-87.7],[31.1,-79.8]];
 map.fitBounds(positions.length ? positions : floridaBounds,{paddingTopLeft:[38,60],paddingBottomRight:[38,38],maxZoom:12});
 group.addTo(map);
} else {document.getElementById('map').textContent='Map libraries could not load. Check your connection. College data is available in the table below.';}
</script></body></html>"""
