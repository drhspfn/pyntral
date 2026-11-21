import { useState } from "react";
import { ArrowRight, Bell, Image as ImageIcon } from "lucide-react";
import type { CustomPageProps } from "@pyntral/types";
import { useAdminFeedback } from "@pyntral/feedback";
import { AsyncSelect, Badge, Button, Card, DatePicker, Dialog, SearchInput, Select, TextInput,
  type SelectOption } from "@pyntral/ui";
import { api } from "@pyntral/api";

/** Demonstrates that extensions use the same UI primitives/theme/feedback as the core. */
export default function Insights({ schema, navigate }: CustomPageProps) {
  const feedback = useAdminFeedback();
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [date, setDate] = useState<string | null>(null);
  const [roles, setRoles] = useState<(string | number)[]>(["reviewer", "author"]);
  const [agentId, setAgentId] = useState<string | number | null>(null);
  const [dialog, setDialog] = useState(false);
  const loadAgents = async (q: string): Promise<SelectOption[]> =>
    (await api<{ items: SelectOption[] }>(`/api/resources/agents/options?q=${encodeURIComponent(q)}`)).items;

  return <section>
    <h1>Component playground</h1>
    <p style={{ color: "var(--ra-muted)", fontSize: 12 }}>A custom page using the public @pyntral/ui and @pyntral/feedback API.</p>
    <div className="resource-grid" style={{ marginBottom: 20 }}>
      <Card title="Reusable controls" description="Light/dark tokens inherited automatically">
        <div style={{ display: "grid", gap: 12 }}>
          <TextInput value={text} onChange={(e) => setText(e.target.value)} placeholder="Regular input" aria-label="Demo input"/>
          <SearchInput value={search} onChange={setSearch} showSubmit submitPosition="outside" onSearch={() => feedback.toast(`Search: ${search}`)}/>
          <Select<string | number> multiple value={roles} onChange={(value) => setRoles(Array.isArray(value) ? value : [])}
            maxItems={2} options={["reviewer", "author", "admin", "reader", "moderator", "support"].map((role) => ({ label: role, value: role }))}/>
          <AsyncSelect value={agentId} onChange={(value) => setAgentId(Array.isArray(value) ? value[0] ?? null : value)}
            loadOptions={loadAgents} placeholder="Find agent (remote search)…"/>
          <DatePicker value={date} onChange={setDate}/>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <Badge tone="success">Active</Badge><Badge tone="primary">Preview</Badge><Badge>Draft</Badge>
          </div>
          <Button variant="primary" startIcon={<Bell size={16}/>} onClick={() => feedback.toast("All controls use the same feedback service", { kind: "success" })}>Show toast</Button>
          <Button variant="secondary" onClick={() => setDialog(true)} startIcon={<ImageIcon size={16}/>}>Open dialog</Button>
        </div>
      </Card>
      <Card title="Registered resources" description={`${schema.resources.length} resources available`}>
        <div style={{ display: "grid", gap: 6 }}>
          {schema.resources.map((resource) => <Button key={resource.id} variant="ghost"
            endIcon={<ArrowRight size={15}/>} onClick={() => navigate(`resources/${resource.id}`)}>
            {resource.label}
          </Button>)}
        </div>
      </Card>
    </div>
    <Dialog open={dialog} onClose={() => setDialog(false)} title="Custom dialog" footer={<Button variant="primary" onClick={() => setDialog(false)}>Close</Button>}>
      <p style={{ color: "var(--ra-text-secondary)" }}>Dialogs can contain any React component, including forms and bridge-backed widgets.</p>
    </Dialog>
  </section>;
}
