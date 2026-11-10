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
  { key: "history", icon: Landmark, tone: "gold", aliases: ["history", "lịch sử", "历史"] },
];

// Official HSK 2025 topic syllabus names (话题大纲), mapped onto the same
// icon/colour set used by the English library so every topic card has a visual.
const HSK_TOPIC_VISUAL_KEYS: Record<string, string> = {
  基本信息: "personal-development", 日常生活: "daily-life", 教育情况: "education",
  职场生活: "work", 文化与传统: "culture", 自然与环境: "environment", 当代社会: "society",
  科学技术: "technology", 个体与社会: "relationships", 国家与社会: "public-policy",
  个人信息: "personal-development", 事件信息: "numbers-time", 物品信息: "home",
  环境信息: "weather", 交往: "communication", 饮食: "food", 交通出行: "travel",
  购物: "shopping", 医疗健康: "health", 休闲: "hobbies", 学习情况: "education",
  校园生活: "school", 工作情况: "work", 职业: "services", 饮食文化: "food",
  家庭生活: "family", 传统习俗: "culture", 姓氏文化: "culture", 个人情况: "personal-development",
  日常事务: "daily-life", 社区: "home", 教育问题: "academic-language", 日常办公: "work",
  职业与经历: "services", 自然: "environment", 环境: "environment", 社会情况: "society",
  文艺: "culture", 体育: "sports", 风俗传统: "culture", 单位情况: "services",
  科技发展: "technology", 科学知识: "science", 概况: "global-issues", 经济现象: "economics",
  社会现象: "society", 中外交流: "global-issues", 语言文字: "academic-language",
  民俗传统: "culture", 人文景观: "travel", 历史: "history", 经营与管理: "leadership",
  传统思想与艺术: "philosophy", 古代科技: "innovation", 人际交往: "relationships",
  形象服饰: "clothing", 饮食餐饮: "food", 建筑与社区: "home", 休闲娱乐: "hobbies",
  学业职业: "education", 人口与发展: "society", 教育发展: "education", 媒介与传播: "media",
  健康与医疗: "health", 交通与运输: "travel", 经济与生产: "economics", 法制与治安: "law",
  社会公共管理: "public-policy", 文学艺术: "literature", 哲学思想: "philosophy",
  习俗礼俗: "culture", 文化遗产: "history", 宇宙环境: "global-issues", 地质环境: "environment",
  大气环境: "weather", 水环境: "environment", 土地环境: "environment", 生物环境: "animals",
  信息科学技术: "technology", 航空航天科学技术: "innovation", 生物科学技术: "science",
  其他新兴科学技术: "innovation",
  // Mascot group for function words.
  基础词汇: "academic-language", 代词与虚词: "academic-language",
};

const topicVisualByAlias = new Map<string, TopicVisualDefinition>();
for (const visual of TOPIC_VISUALS) {
  topicVisualByAlias.set(normalizeTopic(visual.key), visual);
  for (const alias of visual.aliases) topicVisualByAlias.set(normalizeTopic(alias), visual);
}
const visualByKey = new Map(TOPIC_VISUALS.map((visual) => [visual.key, visual]));
for (const [name, key] of Object.entries(HSK_TOPIC_VISUAL_KEYS)) {
  const visual = visualByKey.get(key);
  if (visual && !topicVisualByAlias.has(normalizeTopic(name))) topicVisualByAlias.set(normalizeTopic(name), visual);
}

/** Every HSK syllabus topic name that has a dedicated visual (used by tests). */
export const HSK_TOPIC_NAMES_WITH_VISUALS = Object.keys(HSK_TOPIC_VISUAL_KEYS);

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
