import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  Brain,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  Cpu,
  Crown,
  Earth,
  FlaskConical,
  GraduationCap,
  HeartPulse,
  House,
  Leaf,
  MessageCircle,
  Newspaper,
  Plane,
  School,
  ShoppingBag,
  Users,
  Utensils,
} from "lucide-react";

function normalizeTopic(topic: string): string {
  return topic.trim().toLowerCase();
}

const TOPIC_ICONS: Record<string, LucideIcon> = {
  travel: Plane,
  "basic travel": Plane,
  school: School,
  education: GraduationCap,
  "academic life": GraduationCap,
  family: Users,
  relationships: Users,
  work: BriefcaseBusiness,
  "work & business": BriefcaseBusiness,
  business: BriefcaseBusiness,
  food: Utensils,
  home: House,
  shopping: ShoppingBag,
  health: HeartPulse,
  communication: MessageCircle,
  technology: Cpu,
  innovation: Cpu,
  environment: Leaf,
  "global issues": Earth,
  media: Newspaper,
  science: FlaskConical,
  psychology: Brain,
  leadership: Crown,
  philosophy: BookOpen,
  ethics: BookOpen,
  "global economics": ChartNoAxesCombined,
  "advanced business strategy": ChartNoAxesCombined,
  "literature & criticism": BookOpen,
};

export function getTopicIcon(topic: string): LucideIcon {
  return TOPIC_ICONS[normalizeTopic(topic)] ?? BookOpen;
}

export function getTopicAccent(topic: string): number {
  let value = 0;
  for (const character of normalizeTopic(topic)) value = (value + character.charCodeAt(0)) % 4;
  return value;
}
