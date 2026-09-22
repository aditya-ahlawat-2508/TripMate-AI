import { notFound } from "next/navigation";

import { TripWorkspace } from "@/components/trip-workspace";
import { getTrip } from "@/lib/api";

export default async function TripPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const trip = await getTrip(id);

  if (!trip) notFound();

  return <TripWorkspace trip={trip} />;
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const trip = await getTrip(id);
  const destination = trip?.spec.destination || "a trip";

  return {
    title: `${destination} — planned with TripMate AI`,
    description: `A ${trip?.days.length ?? 0}-day trip to ${destination}, with sourced prices and a real itinerary.`,
  };
}
