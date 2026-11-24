import { useQuery } from "@tanstack/react-query";
import type { DashboardProps } from "@pyntral/types";
import { api } from "@pyntral/api";
import { Badge, Button, Card, Icon } from "@pyntral/ui";

export default function ShopDashboard({ schema, user, group, navigate, defaultView }: DashboardProps) {
  const resources = schema.resources.filter(r => r.capabilities.list &&
    (!group || r.navigation === group.path || r.navigation?.startsWith(group.path + "/")));
  const metrics = resources.filter(r => ["products", "customers", "orders", "agents", "agent-runs"].includes(r.id));
  const query = useQuery({
    queryKey: ["shop-dashboard", group?.path, user.id, metrics.map(r => r.id)],
    queryFn: async () => Promise.all(metrics.map(async r => ({
      resource: r, total: (await api<{total:number}>(`/api/resources/${r.id}?limit=1`)).total,
    }))),
    enabled: metrics.length > 0,
  });
  return <div style={{ display: "grid", gap: 16 }}>
    <Card title={group ? group.path.split("/").at(-1) : "Commerce workspace"}
      description={group ? "Category dashboard" : `Signed in as ${user.display_name ?? user.username}`}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", padding: 12 }}>
        {user.roles.map(role => <Badge key={role} tone="primary">{role}</Badge>)}
        <span>{resources.length} accessible resources</span>
      </div>
      {query.isError && <p role="alert" style={{padding:12}}>Metrics unavailable. Resource links remain available.</p>}
      {query.isLoading && <p style={{padding:12}}>Loading metrics…</p>}
      <div className="resource-grid" style={{padding:12}}>
        {query.data?.map(({resource,total}) => <Card key={resource.id} title={resource.label}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,padding:12}}>
            <strong style={{fontSize:24}}>{total}</strong>
            <Button variant="secondary" startIcon={<Icon icon={resource.icon}/>} onClick={() => navigate(`resources/${resource.id}`)}>Open</Button>
          </div>
        </Card>)}
      </div>
    </Card>
    {defaultView}
  </div>;
}
