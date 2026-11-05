import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { SmilePlus } from "lucide-react"
import {
  commentsAddReactionMutation,
  commentsListReactionsOptions,
  commentsListReactionsQueryKey,
  commentsRemoveReactionMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/design-system"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const reactions = [
  ["👍", "Thumbs up"],
  ["👎", "Thumbs down"],
  ["😄", "Laugh"],
  ["🎉", "Celebrate"],
  ["😕", "Confused"],
  ["❤️", "Heart"],
  ["🚀", "Rocket"],
  ["👀", "Eyes"],
] as const

export const CommentReactions = ({ commentId }: { commentId: string }) => {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const { data, isError, refetch } = useQuery(commentsListReactionsOptions({ path: { comment_id: commentId } }))
  const onSuccess = () =>
    queryClient.invalidateQueries({ queryKey: commentsListReactionsQueryKey({ path: { comment_id: commentId } }) })
  const add = useMutation({ ...commentsAddReactionMutation(), onSuccess, onError: handleError.bind(showErrorToast) })
  const remove = useMutation({
    ...commentsRemoveReactionMutation(),
    onSuccess,
    onError: handleError.bind(showErrorToast),
  })
  const pending = add.isPending || remove.isPending
  return (
    <fieldset className="flex flex-wrap items-center gap-1.5 px-4 pb-3" aria-label="Comment reactions">
      {data?.data.map((reaction) => (
        <Button
          key={reaction.emoji}
          variant="reaction"
          size="xs"
          aria-pressed={reaction.reacted}
          aria-label={`${reaction.emoji} ${reaction.count} ${reaction.count === 1 ? "reaction" : "reactions"}`}
          disabled={pending}
          onClick={() =>
            (reaction.reacted ? remove : add).mutate({
              path: { comment_id: commentId },
              body: { emoji: reaction.emoji as (typeof reactions)[number][0] },
            })
          }
        >
          {reaction.emoji} <span>{reaction.count}</span>
        </Button>
      ))}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="reaction"
            size="icon-xs"
            disabled={pending || !data}
            aria-label="Add reaction"
            title="Add reaction"
          >
            <SmilePlus className="w-3.5 h-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {reactions.map(([emoji, label]) => (
            <DropdownMenuItem
              key={emoji}
              onSelect={() => add.mutate({ path: { comment_id: commentId }, body: { emoji } })}
            >
              {emoji} {label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      {isError && (
        <Button variant="text" size="text" onClick={() => refetch()}>
          Retry loading reactions
        </Button>
      )}
    </fieldset>
  )
}
