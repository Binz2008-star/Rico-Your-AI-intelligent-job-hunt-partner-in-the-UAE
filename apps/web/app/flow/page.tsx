import { redirect } from "next/navigation";

// /applications is the canonical Atelier pipeline route (TASK-20260713-002).
// /flow is kept only so legacy links and the legacy sidebar keep working.
export default function FlowPage() {
  redirect("/applications");
}
