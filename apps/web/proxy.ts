import { clerkMiddleware } from "@clerk/nextjs/server";

// No routes are gated here — planning and viewing trips still work signed
// out (see apps/api/app.py's get_current_user_id, which is optional auth).
// This just makes Clerk's session available via auth()/useAuth() app-wide.
export default clerkMiddleware();

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
