import type { LucideIcon } from "lucide-react";
import {
  BookOpen, Brain, BriefcaseBusiness, Building2, ChartNoAxesCombined, Clock,
  CloudSun, Compass, Cpu, Crown, Dumbbell, Earth, FileText, FlaskConical,
  Gamepad2, GraduationCap, HeartPulse, House, Landmark, Leaf, Lightbulb,
  MessageCircle, MessageSquareText, Newspaper, Palette, PawPrint, Plane, Scale,
  School, Shirt, ShoppingBag, Sparkles, Users, Utensils,
} from "lucide-react";

export type TopicVisualTone =
  | "academic" | "blue" | "coral" | "cyan" | "gold" | "green"
  | "orange" | "red" | "sky" | "teal" | "violet" | "neutral";

interface TopicVisualDefinition {
  key: string;
  icon: LucideIcon;
  tone: TopicVisualTone;
  aliases: string[];
}

function normalizeTopic(topic: string): string {
  return topic.trim().toLocaleLowerCase();
}

const TOPIC_VISUALS: TopicVisualDefinition[] = [
  { key: "family", icon: Users, tone: "teal", aliases: ["family", "gia đình", "家庭"] },
  { key: "school", icon: School, tone: "academic", aliases: ["school", "trường học", "学校"] },
  { key: "daily-life", icon: Clock, tone: "orange", aliases: ["daily life", "cuộc sống hàng ngày", "日常生活"] },
  { key: "food", icon: Utensils, tone: "coral", aliases: ["food", "food & drink", "đồ ăn", "đồ ăn & thức uống", "食物", "饮食"] },
  { key: "home", icon: House, tone: "coral", aliases: ["home", "home & furniture", "nhà cửa", "nhà cửa & nội thất", "家庭与家具", "家居"] },
  { key: "travel", icon: Plane, tone: "blue", aliases: ["basic travel", "travel", "du lịch", "旅行"] },
  { key: "clothing", icon: Shirt, tone: "gold", aliases: ["clothing", "quần áo", "服装", "衣服"] },
  { key: "numbers-time", icon: Clock, tone: "violet", aliases: ["numbers & time", "số & thời gian", "số và thời gian", "数字与时间"] },
  { key: "work", icon: BriefcaseBusiness, tone: "blue", aliases: ["work", "work & career", "work & business", "business", "công việc", "công việc & sự nghiệp", "工作", "商务"] },
  { key: "shopping", icon: ShoppingBag, tone: "green", aliases: ["shopping", "shopping & money", "mua sắm", "mua sắm & tiền bạc", "购物", "购物与金钱"] },
  { key: "health", icon: HeartPulse, tone: "red", aliases: ["health", "health & lifestyle", "sức khỏe", "健康", "健康与生活方式"] },
  { key: "hobbies", icon: Gamepad2, tone: "violet", aliases: ["hobbies", "sở thích", "爱好"] },
  { key: "communication", icon: MessageCircle, tone: "cyan", aliases: ["communication", "giao tiếp", "交流", "沟通"] },
  { key: "services", icon: Building2, tone: "academic", aliases: ["daily services", "dịch vụ hàng ngày", "日常服务"] },
  { key: "relationships", icon: Users, tone: "teal", aliases: ["people & relationships", "relationships", "các mối quan hệ", "con người & quan hệ", "人际关系"] },
  { key: "education", icon: GraduationCap, tone: "academic", aliases: ["education", "academic life", "giáo dục", "đời sống học thuật", "教育", "学术生活"] },
  { key: "environment", icon: Leaf, tone: "green", aliases: ["environment", "môi trường", "环境"] },
  { key: "technology", icon: Cpu, tone: "cyan", aliases: ["technology", "advanced technology", "công nghệ", "科技", "技术"] },
  { key: "media", icon: Newspaper, tone: "violet", aliases: ["media", "truyền thông", "媒体"] },
  { key: "culture", icon: Palette, tone: "orange", aliases: ["culture", "culture & festival", "văn hóa", "văn hóa & lễ hội", "文化", "文化与节日"] },
  { key: "science", icon: FlaskConical, tone: "cyan", aliases: ["science", "khoa học", "科学"] },
  { key: "society", icon: Users, tone: "teal", aliases: ["society", "xã hội", "社会"] },
  { key: "personal-development", icon: Sparkles, tone: "violet", aliases: ["personal development", "phát triển cá nhân", "个人发展"] },
  { key: "leadership", icon: Crown, tone: "gold", aliases: ["leadership", "lãnh đạo", "领导力"] },
  { key: "global-issues", icon: Earth, tone: "green", aliases: ["global issues", "các vấn đề toàn cầu", "全球问题"] },
  { key: "emotions", icon: Brain, tone: "violet", aliases: ["psychology", "emotions", "tâm lý", "cảm xúc", "心理", "情绪"] },
  { key: "innovation", icon: Lightbulb, tone: "gold", aliases: ["innovation", "đổi mới", "创新"] },
  { key: "professional-communication", icon: MessageSquareText, tone: "blue", aliases: ["professional communication", "giao tiếp chuyên nghiệp", "专业沟通"] },
  { key: "philosophy", icon: Compass, tone: "violet", aliases: ["philosophy", "triết học", "哲学"] },
  { key: "ethics", icon: Scale, tone: "violet", aliases: ["ethics", "đạo đức", "伦理"] },
  { key: "public-policy", icon: Landmark, tone: "academic", aliases: ["public policy", "chính sách công", "公共政策"] },
  { key: "economics", icon: ChartNoAxesCombined, tone: "green", aliases: ["global economics", "advanced business strategy", "kinh tế toàn cầu", "全球经济"] },
  { key: "literature", icon: BookOpen, tone: "coral", aliases: ["literature & criticism", "văn học & phê bình", "文学与批评"] },
  { key: "law", icon: Scale, tone: "academic", aliases: ["law & society", "luật & xã hội", "法律与社会"] },
  { key: "academic-language", icon: FileText, tone: "academic", aliases: ["advanced academic language", "ngôn ngữ học thuật nâng cao", "高级学术语言"] },
  { key: "weather", icon: CloudSun, tone: "sky", aliases: ["weather", "thời tiết", "天气"] },
  { key: "animals", icon: PawPrint, tone: "green", aliases: ["animals", "động vật", "动物"] },
  { key: "sports", icon: Dumbbell, tone: "red", aliases: ["sports", "thể thao", "运动"] },
];

const topicVisualByAlias = new Map<string, TopicVisualDefinition>();
for (const visual of TOPIC_VISUALS) {
  topicVisualByAlias.set(normalizeTopic(visual.key), visual);
  for (const alias of visual.aliases) topicVisualByAlias.set(normalizeTopic(alias), visual);
}

const FALLBACK_VISUAL: TopicVisualDefinition = {
  key: "other",
  icon: BookOpen,
  tone: "neutral",
  aliases: [],
};

export function getTopicVisual(topic: string): TopicVisualDefinition {
  return topicVisualByAlias.get(normalizeTopic(topic)) ?? FALLBACK_VISUAL;
}

export function getTopicIcon(topic: string): LucideIcon {
  return getTopicVisual(topic).icon;
}

export function getTopicAccent(topic: string): TopicVisualTone {
  return getTopicVisual(topic).tone;
}
