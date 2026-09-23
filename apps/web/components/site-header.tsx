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
    <header className="sticky top-0 z-20 border-b border-border/80 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3.5">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-sm text-primary-foreground">
            T
          </span>
          TripMate <span className="text-primary">AI</span>
        </Link>
        <div className="flex items-center gap-5">
          {right}
          {isLoaded && isSignedIn && (
            <>
              <Link href="/trips" className="text-sm font-medium text-muted transition hover:text-foreground">
                My Trips
              </Link>
              <Link href="/billing" className="text-sm font-medium text-muted transition hover:text-foreground">
                Billing
              </Link>
              <UserButton />
            </>
          )}
          {isLoaded && !isSignedIn && (
            <SignInButton mode="modal">
              <button className="rounded-lg bg-primary px-3.5 py-1.5 text-sm font-medium text-primary-foreground shadow-sm transition hover:opacity-90">
                Sign in
              </button>
            </SignInButton>
          )}
        </div>
      </div>
    </header>
  );
}
