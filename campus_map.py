"""Leaflet map embedded in Streamlit; browser loads pinned public CDN assets."""
import json

def map_html(markers, focus_id=None, origin=None, radius=None, route=None, routes=None):
    # Escape script delimiters in institutional text before embedding JSON.
    payload = json.dumps(markers, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    settings = json.dumps({"focus": focus_id, "origin": origin, "radius": radius, "route": route, "routes": routes or []}, allow_nan=False).replace("<", "\\u003c")
    return """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<style>
body{margin:0;font:14px sans-serif}
#map{height:100vh;border-radius:16px;background:#102e3c;touch-action:none}
#map:not(.leaflet-container){color:#edf5f3;padding:12px;box-sizing:border-box}
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
.leaflet-container .leaflet-marker-pane .campus-image img{display:block;width:auto;height:auto;max-width:27px!important;max-height:27px!important;object-fit:contain}
.fallback{font-size:19px}
.campus-cluster{background:#123c48;color:#fff;border:2px solid #b5fff0;border-radius:50%;font:bold 13px sans-serif}
.campus-shortlisted{border-color:#12be9a;box-shadow:0 0 0 3px #7af4d9,0 3px 12px #031b2ad9}
.campus-icon.campus-shortlisted::after{background:#12be9a}
.campus-focused{outline:3px solid #ffae58;outline-offset:2px}
.leaflet-tooltip{background:#123440;color:white;border-color:#315463;border-radius:6px}
.leaflet-tooltip-top::before{border-top-color:#315463}
.campus-popup{font:14px/1.4 system-ui,sans-serif;color:#142c3b;overflow-wrap:anywhere}
.campus-popup h3{margin:0 0 6px;font-size:17px;line-height:1.2}
.campus-popup .popup-program{font-weight:600;color:#156657}
.campus-popup details{margin-top:4px}
.campus-popup summary{cursor:pointer}
.campus-popup ul{margin:4px 0;padding-left:20px;max-height:9rem;overflow-y:auto}
.campus-popup dl{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;margin:10px 0}
.campus-popup dt{color:#405a68}
.campus-popup dd{margin:0;font-weight:600}
.campus-popup a{color:#075b50;font-weight:600}
</style></head><body><div id="map" role="region" aria-label="Interactive Florida college map"><p id="map-status">Loading the map… Internet access is needed for map libraries and tiles.</p></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
const schools = """ + payload + """;
const settings = """ + settings + """;
if(typeof L !== 'undefined') {
 const map=L.map('map',{zoomSnap:0.25,scrollWheelZoom:true,touchZoom:true});
 document.getElementById('map-status')?.remove();
 const imagery=L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{
   attribution:'Imagery &copy; <a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9">Esri, Vantor, Earthstar Geographics, and the GIS User Community</a>',
   maxNativeZoom:19,maxZoom:20
 }).addTo(map);
 const streets=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
   attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
   maxNativeZoom:19,maxZoom:20
 });
 const layers=L.control.layers({'Aerial imagery':imagery,'Street map':streets}).addTo(map);
 const group=typeof L.markerClusterGroup==='function' ? L.markerClusterGroup({
   maxClusterRadius:36,
   showCoverageOnHover:false,
   spiderfyOnMaxZoom:true,
   iconCreateFunction:cluster=>{
     const highlighted=cluster.getAllChildMarkers().some(marker=>marker.options.shortlisted);
     return L.divIcon({className:highlighted ? 'campus-cluster campus-shortlisted' : 'campus-cluster',
       html:String(cluster.getChildCount()),iconSize:[34,34]});
   }
 }) : L.layerGroup();
 const positions=[];
 let focusedMarker;
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
   const focused=school.id===settings.focus;
   const iconClass=['campus-icon',school.darkBackground && 'campus-icon-dark',focused && 'campus-focused',
     school.shortlisted && 'campus-shortlisted'].filter(Boolean).join(' ');
   const icon=L.divIcon({className:iconClass,html:content,iconSize:[36,36],iconAnchor:[18,39],tooltipAnchor:[0,-38],popupAnchor:[0,-34]});
   const label=document.createElement('span');label.textContent=school.name;
   const marker=L.marker([school.lat,school.lon],{icon,title:school.name,alt:school.name,shortlisted:school.shortlisted,zIndexOffset:focused ? 2000 : 0})
     .bindTooltip(label).bindPopup(school.popup,{maxWidth:320});
   if(focused) focusedMarker=marker;
   else marker.addTo(group);
   positions.push([school.lat,school.lon]);
 }
 const floridaBounds=[[24.4,-87.7],[31.1,-79.8]];
 if(settings.routes.length){
   const bounds=L.latLngBounds(positions);
   for(const route of settings.routes){
     const label=document.createElement('span');
     label.textContent=route.label;
     const line=L.polyline(route.points,{color:route.color,weight:5,opacity:.95,
       attribution:'Routing by Valhalla / FOSSGIS &copy; OpenStreetMap contributors'}).bindTooltip(label).addTo(map);
     layers.addOverlay(line,label.outerHTML);
     bounds.extend(line.getBounds());
   }
   L.circleMarker(settings.origin,{radius:7,color:'#123440',fillColor:'#fff',fillOpacity:1})
     .bindTooltip('Start near the ZIP center').addTo(map);
   map.fitBounds(bounds,{padding:[38,38],maxZoom:15});
 }
 else if(settings.route) map.fitBounds(settings.route,{padding:[38,38],maxZoom:15});
 else if(focusedMarker) map.setView(focusedMarker.getLatLng(),9);
 else map.fitBounds(positions.length ? positions : floridaBounds,{paddingTopLeft:[38,60],paddingBottomRight:[38,38],maxZoom:9});
 group.addTo(map);
 if(settings.origin && settings.radius){
   L.circle(settings.origin,{radius:settings.radius*1609.344,color:'#35dcc2',fillOpacity:.09,interactive:false}).addTo(map);
 }
 // Keep the focused pin visible at city scale, even when neighboring schools cluster.
 if(settings.route){
   L.polyline(settings.route,{color:'#082437',weight:8,interactive:false}).addTo(map);
   L.polyline(settings.route,{color:'#68e6ff',weight:5,interactive:false,
     attribution:'Routing by <a href="https://valhalla.openstreetmap.de/">Valhalla / FOSSGIS</a> · &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}).addTo(map);
   L.circleMarker(settings.route[0],{radius:7,color:'#082437',weight:3,fillColor:'#68e6ff',fillOpacity:1})
     .bindTooltip('Start near the ZIP center').addTo(map);
 }
 if(focusedMarker){
   focusedMarker.addTo(map);
   if(!settings.route && !settings.routes.length) focusedMarker.openPopup();
 }
} else {document.getElementById('map').textContent='The map could not load. Select List to browse the matching schools.';}
</script></body></html>"""
