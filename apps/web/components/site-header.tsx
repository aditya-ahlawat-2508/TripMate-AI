"use client";

import { SignInButton, useAuth, UserButton } from "@clerk/nextjs";
import Link from "next/link";

// @clerk/nextjs's newest major version ("Core 3") removed the
// <SignedIn>/<SignedOut>/<Protect> control components entirely (they now
// throw on render, pointing at https://clerk.com/err/signedin-is-not-
// available-in-clerk-nextjs) — useAuth()'s isLoaded/isSignedIn is the
// replacement for this kind of conditional rendering.
export function SiteHeader({ right }: { right?: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
        <Link href="/" className="text-lg font-semibold text-primary">
          TripMate AI
        </Link>
        <div className="flex items-center gap-4">
          {right}
          {isLoaded && isSignedIn && (
            <>
              <Link href="/trips" className="text-sm text-foreground hover:text-primary">
                My Trips
              </Link>
              <Link href="/billing" className="text-sm text-foreground hover:text-primary">
                Billing
              </Link>
              <UserButton />
            </>
          )}
          {isLoaded && !isSignedIn && (
            <SignInButton mode="modal">
              <button className="rounded-lg border border-border px-3 py-1.5 text-sm text-foreground hover:bg-card">
                Sign in
              </button>
            </SignInButton>
          )}
        </div>
      </div>
    </header>
  );
}
