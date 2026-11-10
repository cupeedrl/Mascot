/** "Ăn uống (饮食)": Vietnamese name, with the official Chinese name smaller. */
export function TopicName({ topic }: { topic: { name_zh: string; name_vi: string | null } }) {
  if (!topic.name_vi) return <>{topic.name_zh}</>;
  return (
    <>
      {topic.name_vi} <small className="topic-name-zh">({topic.name_zh})</small>
    </>
  );
}
