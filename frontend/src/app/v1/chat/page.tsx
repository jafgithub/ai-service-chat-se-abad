"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import { ChatPage } from "@/components/chat/ChatPage";

/**
 * The booking assistant, at /plumber/v1/chat.
 *
 * `basePath` in next.config.ts supplies the /plumber half, so this file only
 * has to be /v1/chat. The route is versioned because the client asked for it
 * that way and because a second version of the interface is easier to stand up
 * beside the first than to swap underneath it.
 */

function BookingChat() {
  const params = useSearchParams();
  const router = useRouter();
  return <ChatPage scope={params.get("scope") ?? undefined} onBack={() => router.push("/")} />;
}

export default function Page() {
  return (
    <Suspense>
      <BookingChat />
    </Suspense>
  );
}
