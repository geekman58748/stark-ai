import { AuthIntro } from "@/components/auth/auth-intro";
import { AuthScreen } from "@/components/auth/auth-screen";
import { SignUpForm } from "@/components/auth/sign-up-form";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/start/")({
  head: () => ({ meta: [{ title: "Sign up · Stark" }] }),
  component: SignUp,
});

function SignUp() {
  return (
    <AuthScreen step="1 of 3">
      <AuthIntro
        eyebrow="Start for free"
        title="Never run out of light again"
        prompt="Already have an account?"
        link={{ to: "/login", label: "Log in" }}
      />
      <SignUpForm />
    </AuthScreen>
  );
}
