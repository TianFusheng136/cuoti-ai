import { useQuery } from "@tanstack/react-query";

type Health = {
  status: "ok";
};

async function getHealth(): Promise<Health> {
  const response = await fetch("/api/v1/health");
  if (!response.ok) {
    throw new Error("本地服务连接失败");
  }
  return response.json() as Promise<Health>;
}

export function HealthStatus() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: false,
  });

  if (health.isPending) {
    return <span className="service-status is-pending">正在连接本地服务…</span>;
  }
  if (health.isError) {
    return <span className="service-status is-error">本地服务未连接</span>;
  }
  return <span className="service-status is-ok">本地服务已连接</span>;
}
