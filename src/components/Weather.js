import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import './Weather.css';

// Free, no-API-key weather data from Open-Meteo (https://open-meteo.com)
const CITIES = [
  { name: 'New Delhi', country: 'India', latitude: 28.6139, longitude: 77.209 },
  { name: 'Mumbai', country: 'India', latitude: 19.076, longitude: 72.8777 },
  { name: 'Hyderabad', country: 'India', latitude: 17.385, longitude: 78.4867 },
  { name: 'New York', country: 'USA', latitude: 40.7128, longitude: -74.006 },
  { name: 'London', country: 'UK', latitude: 51.5074, longitude: -0.1278 },
  { name: 'Tokyo', country: 'Japan', latitude: 35.6762, longitude: 139.6503 },
];

// WMO weather code -> label, icon, background theme, and a little blurb
const WEATHER_CODES = {
  0: { label: 'Clear sky', icon: '☀️', bg: 'bg-clear', blurb: 'Bright and sunny — great day to be outside!' },
  1: { label: 'Mainly clear', icon: '🌤️', bg: 'bg-clear', blurb: 'Mostly clear skies ahead.' },
  2: { label: 'Partly cloudy', icon: '⛅', bg: 'bg-cloudy', blurb: 'A mix of sun and clouds today.' },
  3: { label: 'Overcast', icon: '☁️', bg: 'bg-cloudy', blurb: 'Grey skies, but dry for now.' },
  45: { label: 'Fog', icon: '🌫️', bg: 'bg-cloudy', blurb: 'Foggy out there — drive safe.' },
  48: { label: 'Rime fog', icon: '🌫️', bg: 'bg-cloudy', blurb: 'Foggy out there — drive safe.' },
  51: { label: 'Light drizzle', icon: '🌦️', bg: 'bg-rain', blurb: 'Light drizzle, keep an umbrella handy.' },
  53: { label: 'Drizzle', icon: '🌦️', bg: 'bg-rain', blurb: 'Light drizzle, keep an umbrella handy.' },
  55: { label: 'Dense drizzle', icon: '🌦️', bg: 'bg-rain', blurb: 'Steady drizzle expected.' },
  61: { label: 'Slight rain', icon: '🌧️', bg: 'bg-rain', blurb: 'Rain showers — grab an umbrella.' },
  63: { label: 'Rain', icon: '🌧️', bg: 'bg-rain', blurb: 'Rainy day, stay cozy indoors.' },
  65: { label: 'Heavy rain', icon: '🌧️', bg: 'bg-rain', blurb: 'Heavy rain — best to stay in.' },
  71: { label: 'Slight snow', icon: '🌨️', bg: 'bg-snow', blurb: 'A little snow is falling.' },
  73: { label: 'Snow', icon: '🌨️', bg: 'bg-snow', blurb: 'Snowy conditions — bundle up!' },
  75: { label: 'Heavy snow', icon: '❄️', bg: 'bg-snow', blurb: 'Heavy snowfall, travel with care.' },
  80: { label: 'Rain showers', icon: '🌦️', bg: 'bg-rain', blurb: 'Passing showers expected.' },
  81: { label: 'Rain showers', icon: '🌦️', bg: 'bg-rain', blurb: 'Passing showers expected.' },
  82: { label: 'Violent showers', icon: '⛈️', bg: 'bg-storm', blurb: 'Intense showers — stay indoors.' },
  95: { label: 'Thunderstorm', icon: '⛈️', bg: 'bg-storm', blurb: 'Thunderstorms nearby — stay safe.' },
  96: { label: 'Storm with hail', icon: '⛈️', bg: 'bg-storm', blurb: 'Thunderstorms with hail possible.' },
  99: { label: 'Storm with hail', icon: '⛈️', bg: 'bg-storm', blurb: 'Thunderstorms with hail possible.' },
};

function describeCode(code) {
  return WEATHER_CODES[code] || { label: 'Unknown', icon: '❓', bg: 'bg-default', blurb: '' };
}

function Weather() {
  const [query, setQuery] = useState('');
  const [selectedCity, setSelectedCity] = useState(CITIES[0]);
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const filteredCities = useMemo(
    () =>
      CITIES.filter((c) =>
        `${c.name} ${c.country}`.toLowerCase().includes(query.trim().toLowerCase())
      ),
    [query]
  );

  useEffect(() => {
    setLoading(true);
    setError(null);

    const url = `https://api.open-meteo.com/v1/forecast?latitude=${selectedCity.latitude}&longitude=${selectedCity.longitude}&current=temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code`;

    axios
      .get(url)
      .then((response) => {
        setWeather(response.data.current);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [selectedCity]);

  const condition = weather ? describeCode(weather.weather_code) : describeCode(null);

  return (
    <div className={`weather-app ${condition.bg}`}>
      <div className="weather-container">
        <h1 className="weather-title">🌈 Weather Now</h1>

        <div className="city-search">
          <input
            type="text"
            placeholder="Search a city..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="city-chips">
          {filteredCities.length === 0 && (
            <span className="city-chip-empty">No cities match "{query}"</span>
          )}
          {filteredCities.map((city) => (
            <button
              key={city.name}
              className={`city-chip ${city.name === selectedCity.name ? 'active' : ''}`}
              onClick={() => setSelectedCity(city)}
            >
              {city.name}
            </button>
          ))}
        </div>

        {loading && <p className="weather-status">Loading weather...</p>}
        {error && <p className="weather-status">Couldn't load weather: {error}</p>}

        {!loading && !error && weather && (
          <div className="weather-card">
            <p className="weather-card-city">{selectedCity.name}</p>
            <p className="weather-card-country">{selectedCity.country}</p>

            <div className="weather-icon-big">{condition.icon}</div>
            <p className="weather-temp-big">{Math.round(weather.temperature_2m)}°</p>
            <p className="weather-label-big">{condition.label}</p>

            <div className="weather-stats">
              <div>
                <p className="weather-stat-value">{Math.round(weather.apparent_temperature)}°</p>
                <p className="weather-stat-label">Feels like</p>
              </div>
              <div>
                <p className="weather-stat-value">{weather.relative_humidity_2m}%</p>
                <p className="weather-stat-label">Humidity</p>
              </div>
              <div>
                <p className="weather-stat-value">{weather.wind_speed_10m} km/h</p>
                <p className="weather-stat-label">Wind</p>
              </div>
            </div>

            <p className="weather-blurb">{condition.blurb}</p>
            <p className="weather-updated">Updated {new Date().toLocaleTimeString()}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Weather;
