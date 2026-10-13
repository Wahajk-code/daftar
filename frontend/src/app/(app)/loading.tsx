import { LoadingBlock } from "@/components/ui/States";

/** Shown while a signed-in screen is being fetched: the shape of a list screen, so the page never flashes empty. */
export default function Loading() {
  return <LoadingBlock shape="page" label="Loading the screen" />;
}
