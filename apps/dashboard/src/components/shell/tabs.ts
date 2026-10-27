import { Icons } from "@stark/ui/components/icons";

export const tabs = [
  { to: "/", label: "Home", icon: Icons.Home, exact: true },
  { to: "/bills", label: "Bills", icon: Icons.Bills, exact: false },
  { to: "/activity", label: "Activity", icon: Icons.Activity, exact: false },
  { to: "/wallet", label: "Wallet", icon: Icons.Wallet, exact: false },
  { to: "/settings", label: "Settings", icon: Icons.Settings, exact: false },
] as const;
