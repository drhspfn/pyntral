import { useState } from "react";
import { ArrowRight, Bell, Image as ImageIcon } from "lucide-react";
import type { CustomPageProps } from "@pyntral/types";
import { useAdminFeedback } from "@pyntral/feedback";
import { AsyncSelect, Badge, Button, Card, Checkbox, CheckboxGroup, DatePicker, Dialog, FileUpload, formatFileRejection, Popover, PopoverTrigger, PopoverContent, PopoverHeader, PopoverFooter, RadioGroup, SearchInput, Select, SortableList, Switch, TextInput, ToggleGroup,
  type SelectOption } from "@pyntral/ui";

import { api } from "@pyntral/api";

/** Demonstrates that extensions use the same UI primitives/theme/feedback as the core. */
export default function Insights({ schema, navigate }: CustomPageProps) {
  const feedback = useAdminFeedback();
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [date, setDate] = useState<string | null>(null);
  const [demoFiles, setDemoFiles] = useState<File[]>([]);
  const [singleDemoFiles, setSingleDemoFiles] = useState<File[]>([]);
  const [roles, setRoles] = useState<(string | number)[]>(["reviewer", "author"]);
  const [agentId, setAgentId] = useState<string | number | null>(null);
  const [dialog, setDialog] = useState(false);
  const [alerts, setAlerts] = useState(true);
  const [pinned, setPinned] = useState(false);
  const [channels, setChannels] = useState<string[]>(["email", "in-app"]);
  const [priority, setPriority] = useState<string | null>("standard");
  const [density, setDensity] = useState<string | null>("comfortable");
  const [workflowSteps, setWorkflowSteps] = useState([
    { id: "review", label: "Review request" },
    { id: "approve", label: "Approve changes" },
    { id: "publish", label: "Publish update" },
  ]);
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
      <Card title="Choice controls" description="Shared Checkbox, Switch, CheckboxGroup, RadioGroup and ToggleGroup atoms">
        <div style={{ display: "grid", gap: 17, padding: 14 }}>
          <Checkbox checked={pinned} onCheckedChange={setPinned} label="Pin example"
            description="Controlled checkbox with themed focus state"/>
          <Switch checked={alerts} onCheckedChange={setAlerts} label="Enable alerts"/>
          <CheckboxGroup<string> label="Notification channels" value={channels} onValueChange={setChannels}
            maxSelected={2} options={[
              { value: "email", label: "Email" }, { value: "in-app", label: "In-app" },
              { value: "sms", label: "SMS (choose up to two)" },
            ]}/>
          <RadioGroup<string> label="Priority (exactly one)" value={priority} onValueChange={setPriority}
            options={[{ value: "standard", label: "Standard" }, { value: "urgent", label: "Urgent" }]}/>
          <ToggleGroup<string> label="Table density" value={density} onValueChange={(next) => {
            if (typeof next === "string") setDensity(next);
          }} options={[{ value: "comfortable", label: "Comfortable" }, { value: "compact", label: "Compact" }]}/>
        </div>
      </Card>
      <Card title="Drag to reorder" description="Shared SortableList with mouse, touch and keyboard support">
        <div style={{ padding: "10px 0" }}>
          <SortableList items={workflowSteps} getKey={(step) => step.id} getLabel={(step) => step.label}
            ariaLabel="Workflow steps" onReorder={setWorkflowSteps}
            renderItem={(step, index) => <span style={{ flex: 1, padding: "9px 4px", fontSize: 12 }}>
              <strong>{index + 1}.</strong> {step.label}
            </span>}/>
        </div>
      </Card>
      <Card title="Popover playground" description="Shared portal with viewport flip, sizing and hover/click modes">
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 14 }}>
          <Popover interaction="click">
            <PopoverTrigger asChild><Button variant="secondary">Open click popover</Button></PopoverTrigger>
            <PopoverContent width={340} minHeight={180} maxHeight={400}>
              <PopoverHeader><strong>Popover settings</strong></PopoverHeader>
              <p style={{ fontSize: 12 }}>The panel stays inside the viewport and flips above its trigger when necessary.</p>
              <Select<string> value={priority} onChange={(value) => {
                if (typeof value === "string") setPriority(value);
              }} searchable={false} clearable={false} options={[
                { value: "standard", label: "Standard" }, { value: "urgent", label: "Urgent" },
              ]}/>
              <PopoverFooter><span style={{ color: "var(--ra-muted)", fontSize: 11 }}>Click outside or press Escape to close</span></PopoverFooter>
            </PopoverContent>
          </Popover>
          <Popover interaction="hover" openDelay={250} closeDelay={250}>
            <PopoverTrigger asChild><Button variant="ghost">Hover for details</Button></PopoverTrigger>
            <PopoverContent width={260} minHeight={80} maxHeight={240}>
              <strong>Hover card</strong>
              <p style={{ fontSize: 12, marginTop: 8 }}>Pointer may move between the trigger and portal.</p>
            </PopoverContent>
          </Popover>
        </div>
      </Card>
      <Card title="File upload (mock)" description="No requests are made; file bytes stay in this browser">
        <div style={{ display: "grid", gap: 16 }}>
          <FileUpload files={demoFiles} onFilesChange={setDemoFiles}
            multiple maxFiles={4} maxSizeBytes={2 * 1024 * 1024}
            maxTotalBytes={6 * 1024 * 1024} accept="image/png,image/jpeg,image/webp,application/pdf"
            preview allowPaste onRejected={(errors) => feedback.toast(
              errors.map(error => formatFileRejection(error, {
                multiple: true, maxFiles: 4, maxSizeBytes: 2 * 1024 * 1024,
                maxTotalBytes: 6 * 1024 * 1024,
                accept: "image/png,image/jpeg,image/webp,application/pdf",
              })).join(" "), { kind: "error", duration: 6500 })}/>
          <FileUpload files={singleDemoFiles} onFilesChange={setSingleDemoFiles}
            multiple={false} maxFiles={1} accept="image/png,image/jpeg"
            preview={false} allowPaste={false} label="Choose one image (without preview)"/>
          <div style={{ fontSize: 12, color: "var(--ra-muted)" }}>
            Selected: {demoFiles.length + singleDemoFiles.length} · No backend upload or file entity created
          </div>
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
