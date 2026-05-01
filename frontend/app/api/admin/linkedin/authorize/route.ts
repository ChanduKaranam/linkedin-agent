import { NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  // Redirect the browser directly to the backend OAuth start endpoint
  // (backend does the 302 to LinkedIn)
  return NextResponse.redirect(`${BACKEND}/admin/linkedin/authorize`);
}
