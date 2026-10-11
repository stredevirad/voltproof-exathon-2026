import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, Skeleton, useApi } from "../ui";
import { GroupPanel } from "./EventView";

export default function GroupView() {
  const [sp] = useSearchParams();
  const key = sp.get("key") || "";
  const { data, error, loading } = useApi(() => api.group(key), [key]);
  if (loading && !data) return <Skeleton height={300} label="the potential shared supply event" />;
  if (error) return <ErrorBox error={error} what="this potential shared supply event" />;
  if (!data) return null;
  return (<><h1>Potential shared supply event</h1><GroupPanel g={data} /></>);
}
