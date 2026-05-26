import type { GPUInfo } from '@/shared/types/api.gen';

export type GpuStatus = 'normal' | 'warning' | 'danger';

export function getGpuStatus(gpu: GPUInfo): GpuStatus {
  if (gpu.tempC !== undefined) {
    if (gpu.tempC > 85) return 'danger';
    if (gpu.tempC > 75) return 'warning';
  }
  const memoryPercent = (gpu.usedMB / gpu.totalMB) * 100;
  if (memoryPercent > 95) return 'danger';
  if (memoryPercent > 80) return 'warning';
  return 'normal';
}

export function getTemperatureColor(tempC: number): string {
  if (tempC > 85) return '#ef4444';
  if (tempC > 75) return '#ff6600';
  if (tempC >= 60) return '#f59e0b';
  return '#00cfaa';
}

export function calculateNodeStats(gpus: GPUInfo[]) {
  const validGpus = gpus.filter(g => g.totalMB > 0);
  if (validGpus.length === 0) {
    return { avgTemperature: 0, totalMemoryUsed: 0, totalMemoryAvailable: 0, avgUtilization: 0 };
  }
  return {
    avgTemperature: Math.round(validGpus.reduce((sum, g) => sum + (g.tempC || 0), 0) / validGpus.length),
    totalMemoryUsed: validGpus.reduce((sum, g) => sum + g.usedMB, 0),
    totalMemoryAvailable: validGpus.reduce((sum, g) => sum + g.totalMB, 0),
    avgUtilization: Math.round(validGpus.reduce((sum, g) => sum + (g.utilization || 0), 0) / validGpus.length),
  };
}

export function getMemoryPercent(gpu: GPUInfo): number {
  if (gpu.totalMB === 0) return 0;
  return Math.round((gpu.usedMB / gpu.totalMB) * 100);
}

export function formatMemoryGB(mb: number): string {
  return (mb / 1024).toFixed(1);
}
