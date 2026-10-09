import { CaseWorkspace } from "@/components/case-workspace";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ view?: string }>;
}) {
  const { id } = await params;
  const { view } = await searchParams;
  return <CaseWorkspace key={id} id={id} initialView={view} />;
}
