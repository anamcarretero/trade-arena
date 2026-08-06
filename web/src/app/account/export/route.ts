import {NextResponse} from "next/server";
import {apiFetch} from "@/lib/api";

export async function GET() {
  const response = await apiFetch("/api/v1/me");
  if (response.status === 403) {
    return NextResponse.json({error: "forbidden"}, {status: 403});
  }
  if (!response.ok) {
    return NextResponse.json({error: "export_failed"}, {status: 502});
  }
  const exportData = await response.json();
  return new NextResponse(`${JSON.stringify(exportData, null, 2)}\n`, {
    status: 200,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Disposition": "attachment; filename=tradearena-account-export.json",
      "Cache-Control": "no-store"
    }
  });
}
