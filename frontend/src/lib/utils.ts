import { type ClassValue, clsx } from "clsx";
import { useEffect, useState } from "react";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
// // from identityQuery.data.uptime_centiseconds
// export function localUpTimeUpdater(startTime: number, callback: (uptime: number) => void): () => void {
//   let current: number = startTime;
//   const updateUptime = () => {
//     current += 100;
//     callback(current);
//   };

//   const intervalId = setInterval(updateUptime, 1000);
//   updateUptime(); // Initial call to set the uptime immediately

//   return () => clearInterval(intervalId); // Return a function to clear the interval
// }

export function useLiveUptime(formatter: (uptime: number) => string, startTimeCentiseconds?: number): string {
  const [currentCentiseconds, setCurrentCentiseconds] = useState(startTimeCentiseconds ?? 0);

  useEffect(() => {
    if (startTimeCentiseconds === undefined) return;
    let current = startTimeCentiseconds;
    const interval = setInterval(() => {
      current += 10;
      setCurrentCentiseconds(current);
    }, 100);
    return () => clearInterval(interval);
  }, [startTimeCentiseconds]);

  return formatter(currentCentiseconds);
}