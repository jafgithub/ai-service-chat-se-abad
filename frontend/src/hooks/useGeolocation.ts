"use client";

import { useState, useCallback } from "react";

export interface GeoPosition {
  latitude: number;
  longitude: number;
}

interface UseGeolocationReturn {
  position: GeoPosition | null;
  error: string | null;
  isRequesting: boolean;
  requestLocation: () => Promise<GeoPosition | null>;
}

export function useGeolocation(): UseGeolocationReturn {
  const [position, setPosition] = useState<GeoPosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRequesting, setIsRequesting] = useState(false);

  const requestLocation = useCallback((): Promise<GeoPosition | null> => {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        setError("Geolocation is not supported by your browser.");
        resolve(null);
        return;
      }

      setIsRequesting(true);
      setError(null);

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const geo: GeoPosition = {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
          };
          setPosition(geo);
          setIsRequesting(false);
          resolve(geo);
        },
        (err) => {
          const msg =
            err.code === 1
              ? "Location access denied. You can still place orders manually."
              : "Unable to retrieve your location.";
          setError(msg);
          setIsRequesting(false);
          resolve(null);
        },
        { timeout: 8000, maximumAge: 60000 }
      );
    });
  }, []);

  return { position, error, isRequesting, requestLocation };
}
