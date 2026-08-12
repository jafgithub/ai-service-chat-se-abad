"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import { ChatPage } from "@/components/chat/ChatPage";

function ChatPageWrapper() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const scope = searchParams.get("scope") ?? undefined;

  return <ChatPage scope={scope} onBack={() => router.push("/")} />;
}

export default function Page() {
  return (
    <Suspense>
      <ChatPageWrapper />
    </Suspense>
  );
}
