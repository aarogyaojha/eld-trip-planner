import React from 'react'
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'

const ICON_COLORS = {
  location: '#5b9bd5',
  break: '#ffc857',
  fuel: '#3fb68b',
  rest: '#8d7bd8',
  restart: '#e0524b',
}

function makeIcon(color) {
  return L.divIcon({
    className: 'stop-marker',
    html: `<span style="background:${color}"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  })
}

export default function RouteMap({ route, stops, locations }) {
  if (!route || !route.geometry || route.geometry.length === 0) {
    return <div className="map-placeholder">Plan a trip to see the route, stops, and rest breaks here.</div>
  }

  const center = route.geometry[Math.floor(route.geometry.length / 2)]

  return (
    <MapContainer center={center} zoom={6} className="route-map">
      <TileLayer
        attribution='&copy; <a href="https://carto.com/attributions">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      <Polyline positions={route.geometry} pathOptions={{ color: '#ff7a33', weight: 4 }} />

      {locations && (
        <>
          <Marker position={[locations.current.lat, locations.current.lon]} icon={makeIcon('#5b9bd5')}>
            <Popup>Current location</Popup>
          </Marker>
          <Marker position={[locations.pickup.lat, locations.pickup.lon]} icon={makeIcon('#ff7a33')}>
            <Popup>Pickup</Popup>
          </Marker>
          <Marker position={[locations.dropoff.lat, locations.dropoff.lon]} icon={makeIcon('#e7e9f0')}>
            <Popup>Drop-off</Popup>
          </Marker>
        </>
      )}

      {stops &&
        stops
          .filter((s) => s.kind !== 'location')
          .map((stop, idx) => (
            <Marker
              key={idx}
              position={[stop.location[0], stop.location[1]]}
              icon={makeIcon(ICON_COLORS[stop.kind] || '#8c93a8')}
            >
              <Popup>
                <strong>{stop.label}</strong>
                <br />
                {stop.city}
                <br />
                {new Date(stop.time).toLocaleString()}
              </Popup>
            </Marker>
          ))}
    </MapContainer>
  )
}
