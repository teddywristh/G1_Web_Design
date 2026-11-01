export async function GET() {
  try {
    const origin =
      process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    const response = await fetch(`${origin.replace(/\/$/, "")}/health`, {
      signal: AbortSignal.timeout(3000),
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Backend unavailable");
    const data = await response.json();
    return Response.json({ connected: data.status === "ok" });
  } catch {
    return Response.json({ connected: false });
  }
}
