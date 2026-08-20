import type { LucideIcon } from "lucide-react";
import {
  Atom,
  BookOpen,
  Brain,
  BriefcaseBusiness,
  Building2,
  ChartNoAxesCombined,
  Clock,
  Compass,
  Cpu,
  Crown,
  Earth,
  FileText,
  FlaskConical,
  Gamepad2,
  GraduationCap,
  HeartPulse,
  House,
  Landmark,
  Layers,
  Leaf,
  Lightbulb,
  MessageCircle,
  MessageSquareText,
  Newspaper,
  Palette,
  Plane,
  Scale,
  School,
  Shirt,
  ShoppingBag,
  Sparkles,
  Users,
  Utensils,
} from "lucide-react";

function normalizeTopic(topic: string): string {
  return topic.trim().toLowerCase();
}

const TOPIC_ICONS: Record<string, LucideIcon> = {
  // A1
  family: Users,
  school: School,
  "daily life": Clock,
  food: Utensils,
  home: House,
  "basic travel": Plane,
  clothing: Shirt,
  "numbers & time": Clock,

  // A2
  travel: Plane,
  work: BriefcaseBusiness,
  shopping: ShoppingBag,
  health: HeartPulse,
  hobbies: Gamepad2,
  communication: MessageCircle,
  "daily services": Building2,
  "people & relationships": Users,

  // B1
  education: GraduationCap,
  environment: Leaf,
  technology: Cpu,
  relationships: Users,
  "work & career": BriefcaseBusiness,
  "health & lifestyle": HeartPulse,

  // B2
  business: BriefcaseBusiness,
  "work & business": BriefcaseBusiness,
  media: Newspaper,
  culture: Palette,
  science: FlaskConical,
  society: Users,
  "personal development": Sparkles,

  // C1
  leadership: Crown,
  "global issues": Earth,
  psychology: Brain,
  innovation: Lightbulb,
  "academic life": GraduationCap,
  "professional communication": MessageSquareText,
  "advanced technology": Cpu,

  // C2
  philosophy: Compass,
  ethics: Scale,
  "public policy": Landmark,
  "global economics": ChartNoAxesCombined,
  "literature & criticism": BookOpen,
  "advanced business strategy": ChartNoAxesCombined,
  "law & society": Scale,
  "advanced academic language": FileText,
};

export function getTopicIcon(topic: string): LucideIcon {
  return TOPIC_ICONS[normalizeTopic(topic)] ?? BookOpen;
}

export function getTopicAccent(topic: string): number {
  let value = 0;
  for (const character of normalizeTopic(topic)) value = (value + character.charCodeAt(0)) % 4;
  return value;
}
