import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-6 text-center">
      <h1 className="text-2xl font-semibold text-foreground">Trip not found</h1>
      <p className="text-muted">This trip doesn&apos;t exist, or the link is wrong.</p>
      <Link href="/" className="mt-2 text-primary underline">
        Plan a new trip
      </Link>
    </div>
  );
}
