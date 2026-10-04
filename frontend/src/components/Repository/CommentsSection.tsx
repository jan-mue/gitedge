import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { MessageSquare } from "lucide-react"
import { useState } from "react"

import { CommentsService } from "@/client"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface CommentsSectionProps {
  owner: string
  repo: string
  number: number
}

const CommentsSection = ({ owner, repo, number }: CommentsSectionProps) => {
  const repoPath = `${owner}/${repo}.git`
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const [body, setBody] = useState("")

  const { data } = useQuery({
    queryKey: ["comments", repoPath, number],
    queryFn: async () => (await CommentsService.listComments({ path: { path: repoPath, number } })).data,
  })

  const mutation = useMutation({
    mutationFn: (commentBody: string) =>
      CommentsService.createComment({
        path: { path: repoPath, number },
        body: { body: commentBody },
      }),
    onSuccess: () => {
      setBody("")
      queryClient.invalidateQueries({ queryKey: ["comments", repoPath, number] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const comments = data?.data ?? []

  return (
    <div className="space-y-4" data-testid="comments-section">
      <h2 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
        <MessageSquare className="w-4 h-4" />
        {data?.count ?? 0} {data?.count === 1 ? "comment" : "comments"}
      </h2>

      {comments.length > 0 && (
        <div className="space-y-3">
          {comments.map((comment) => (
            <div
              key={comment.id}
              className="border border-border rounded-lg bg-card"
              data-testid={`comment-${comment.id}`}
            >
              <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-secondary/50 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">
                  {comment.author_username ?? comment.author_email ?? "unknown"}
                </span>
                {comment.created_at && <span>commented {new Date(comment.created_at).toLocaleString()}</span>}
              </div>
              <p className="px-4 py-3 text-sm text-foreground whitespace-pre-wrap break-words">{comment.body}</p>
            </div>
          ))}
        </div>
      )}

      <div className="border border-border rounded-lg overflow-hidden">
        <textarea
          id="comment-body"
          name="comment-body"
          rows={4}
          placeholder="Leave a comment"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          data-testid="comment-input"
          className="w-full px-3 py-2 text-sm bg-card text-foreground placeholder:text-muted-foreground focus:outline-none resize-y"
        />
        <div className="flex items-center justify-end px-3 py-2 border-t border-border bg-secondary/50">
          <Button
            size="sm"
            disabled={!body.trim() || mutation.isPending}
            onClick={() => mutation.mutate(body)}
            data-testid="comment-submit"
          >
            {mutation.isPending ? "Commenting..." : "Comment"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default CommentsSection
