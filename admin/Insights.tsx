import { useState } from "react";
import { ArrowRight, Bell, Image as ImageIcon } from "lucide-react";
import type { CustomPageProps } from "@pyntral/types";
import { useAdminFeedback } from "@pyntral/feedback";
import { AsyncSelect, Badge, Button, Card, Checkbox, CheckboxGroup, Collapsible, DatePicker, Dialog, FileUpload, FileRow, Icon, OverflowText, formatFileRejection, Popover, PopoverTrigger, PopoverContent, PopoverHeader, PopoverFooter, RadioGroup, SearchInput, Select, SortableList, Switch, TextInput, ToggleGroup,
  type SelectOption } from "@pyntral/ui";

import { api } from "@pyntral/api";
import { inspectUpload } from "@pyntral/generated";
import { Tabs, TabList, Tab, TabPanel, DataTable, Table, CodeBlock, JsonView, type DataTableProps } from "@pyntral/ui";

/** Demonstrates that extensions use the same UI primitives/theme/feedback as the core. */
export default function Insights({ schema, navigate }: CustomPageProps) {
  const feedback = useAdminFeedback();
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [date, setDate] = useState<string | null>(null);
  const [demoFiles, setDemoFiles] = useState<File[]>([]);
  const [binaryFiles, setBinaryFiles] = useState<File[]>([]);
  const [demoTab, setDemoTab] = useState("table");
  const [demoSort, setDemoSort] = useState<DataTableProps<{ id: string; label: string }>["sort"]>();
  const [binaryResult, setBinaryResult] = useState<{ name: string; size: number; sha256: string } | null>(null);
  const [singleDemoFiles, setSingleDemoFiles] = useState<File[]>([]);
  const [roles, setRoles] = useState<(string | number)[]>(["reviewer", "author"]);
  const [agentId, setAgentId] = useState<string | number | null>(null);
  const [dialog, setDialog] = useState(false);
  const [disclosureOpen, setDisclosureOpen] = useState(false);
  const [showExampleFile, setShowExampleFile] = useState(true);
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
  const tableRows = demoSort ? [...workflowSteps].sort((a, b) => {
    const key = demoSort.column === "id" ? "id" : "label";
    return a[key].localeCompare(b[key]) * (demoSort.direction === "asc" ? 1 : -1);
  }) : workflowSteps;
  const loadAgents = async (q: string): Promise<SelectOption[]> =>
    (await api<{ items: SelectOption[] }>(`/api/resources/agents/options?q=${encodeURIComponent(q)}`)).items;

  return <section>
    <h1>Component playground</h1>
    <p style={{ color: "var(--ra-muted)", fontSize: 12 }}>A custom page using the public @pyntral/ui and @pyntral/feedback API.</p>
    <Card title="Consumer extension primitives" description="Tabs, DataTable and typed binary bridge">
      <Tabs value={demoTab} onValueChange={setDemoTab}>
        <TabList label="Consumer examples"><Tab value="table">DataTable</Tab><Tab value="native">Table</Tab><Tab value="upload">Binary upload</Tab><Tab value="disabled" disabled>Disabled</Tab></TabList>
        <TabPanel value="table"><DataTable rows={tableRows} getRowKey={row => row.id}
          label="Workflow steps" compact={density === "compact"} sort={demoSort} onSortChange={setDemoSort}
          columns={[{ id: "id", header: "ID", cell: row => row.id, sortable: true }, { id: "label", header: "Step", cell: row => row.label, sortable: true }]}/></TabPanel>
        <TabPanel value="native"><Table label="Native table example" compact={density === "compact"}>
          <thead><tr><th scope="col">Primitive</th><th scope="col">Usage</th></tr></thead>
          <tbody><tr><td>Table</td><td>Custom semantic markup</td></tr><tr><td>DataTable</td><td>Typed row and column definitions</td></tr></tbody>
        </Table></TabPanel>
        <TabPanel value="disabled">This panel cannot be selected.</TabPanel>
        <TabPanel value="upload" keepMounted><FileUpload files={binaryFiles} onFilesChange={setBinaryFiles} multiple={false}
          maxSizeBytes={2_000_000} accept="image/png,image/jpeg" onUpload={async (file, ctx) => {
            const result = await inspectUpload({ label: "demo" }, file, ctx.signal);
            setBinaryResult(result);
            return { key: result.sha256, name: result.name, size: result.size, mimeType: file.type };
          }}/>{binaryResult && <p style={{ overflowWrap: "anywhere" }}>{binaryResult.name} · {binaryResult.size} bytes · SHA-256 {binaryResult.sha256}</p>}</TabPanel>
      </Tabs>
    </Card>
    <div className="resource-grid" style={{ marginTop: 20, marginBottom: 20 }}>
      <Card title="Code and JSON viewers" description="Read-only, copyable, collapsible and theme-aware">
        <div style={{display:"grid",gap:12,padding:12,minWidth:0}}>
          <CodeBlock title="C# example" code={'using System;\npublic class Demo {\n    public static void Main() { Console.WriteLine("Hello"); }\n}'} collapsible maxHeight={180}/>
          <JsonView title="Request payload" value={{ status: "ok", count: 12, data: { active: true, tags: ["demo", "shop"] } }} collapsible maxHeight={200}/>
          <CodeBlock code="SELECT * FROM products" language="sql" inline/>
          <CodeBlock title="Plain log" code="Processing complete\nNo errors" language="plaintext" highlight={false} formatToggle={false} wrap maxHeight={120}/>
        </div>
      </Card>
      <Card title="Uncontrolled tabs" description="Local selection owned by Tabs">
        <Tabs defaultValue="first"><TabList label="Local tabs"><Tab value="first">First</Tab><Tab value="second">Second</Tab></TabList>
          <TabPanel value="first">No external state required.</TabPanel><TabPanel value="second">Keyboard navigation is shared.</TabPanel></Tabs>
      </Card>
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
      <Card title="Disclosure and icon primitives" description="Controlled disclosure, overflow tooltip and dynamic icons">
        <div style={{ display: "grid", gap: 12, minWidth: 0 }}>
          <Collapsible header={<span style={{ display: "flex", alignItems: "center", gap: 6 }}><Icon icon="settings-2"/> Advanced settings</span>}
            open={disclosureOpen} onOpenChange={setDisclosureOpen}
            actions={<Button type="button" variant="ghost" onClick={() => feedback.toast("Header action")}>Action</Button>}>
            <p style={{ margin: 0, fontSize: 12 }}>Header actions work independently of the disclosure.</p>
          </Collapsible>
          <div style={{ width: "min(100%, 150px)" }}>
            <OverflowText>A long label that needs a tooltip</OverflowText>
          </div>
          <div style={{ display: "flex", gap: 10 }}><Icon icon="shopping-cart" size={20}/><Icon icon="truck" size={20}/><Icon icon="chart-column" size={20}/></div>
          {showExampleFile ? <FileRow name="example-attachment.pdf" size={152400} mimeType="application/pdf"
            onRemove={() => setShowExampleFile(false)}/> :
            <Button type="button" onClick={() => setShowExampleFile(true)}>Restore example row</Button>}
        </div>
      </Card>
      <Card title="Registered resources" description={`${schema.resources.length} resources available`}>
        <div style={{ display: "grid", gap: 6 }}>
          {schema.resources.map((resource) => <Button key={resource.id} variant="ghost"
            startIcon={<Icon icon={resource.icon}/>} endIcon={<ArrowRight size={15}/>} onClick={() => navigate(`resources/${resource.id}`)}>
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
