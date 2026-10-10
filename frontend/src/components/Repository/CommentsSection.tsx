import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { MessageSquare } from "lucide-react"
import { useState } from "react"

import {
  commentsCreateCommentMutation,
  commentsDeleteCommentMutation,
  commentsListCommentsOptions,
  commentsListCommentsQueryKey,
  commentsUpdateCommentMutation,
} from "@/client/@tanstack/react-query.gen"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface CommentsSectionProps {
  owner: string
  repo: string
  number: number
}

const CommentsSection = ({ owner, repo, number }: CommentsSectionProps) => {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const { user } = useAuth()
  const [body, setBody] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editBody, setEditBody] = useState("")

  const { data } = useQuery({
    ...commentsListCommentsOptions({ path: { owner, repo, number } }),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: commentsListCommentsQueryKey({ path: { owner, repo, number } }) })

  const mutation = useMutation({
    ...commentsCreateCommentMutation(),
    onSuccess: () => {
      setBody("")
      invalidate()
    },
    onError: handleError.bind(showErrorToast),
  })

  const editMutation = useMutation({
    ...commentsUpdateCommentMutation(),
    onSuccess: () => {
      setEditingId(null)
      setEditBody("")
      invalidate()
    },
    onError: handleError.bind(showErrorToast),
  })

  const deleteMutation = useMutation({
    ...commentsDeleteCommentMutation(),
    onSuccess: () => invalidate(),
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
                <span className="font-medium text-foreground">{comment.author_username}</span>
                <span>commented {new Date(comment.created_at).toLocaleString()}</span>
                {comment.author_username === user?.name && editingId !== comment.id && (
                  <div className="ml-auto flex items-center gap-2">
                    <button
                      type="button"
                      className="text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => {
                        setEditingId(comment.id)
                        setEditBody(comment.body)
                      }}
                      data-testid={`edit-comment-${comment.id}`}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="text-xs text-muted-foreground hover:text-destructive"
                      disabled={deleteMutation.isPending}
                      onClick={() => {
                        if (window.confirm("Delete this comment?"))
                          deleteMutation.mutate({ path: { comment_id: comment.id } })
                      }}
                      data-testid={`delete-comment-${comment.id}`}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
              {editingId === comment.id ? (
                <div className="space-y-2 px-4 py-3">
                  <textarea
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                    data-testid={`edit-comment-input-${comment.id}`}
                    className="w-full rounded border border-border bg-card px-3 py-2 text-sm text-foreground focus:outline-none resize-y"
                  />
                  <div className="flex justify-end gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditingId(null)
                        setEditBody("")
                      }}
                      data-testid={`edit-comment-cancel-${comment.id}`}
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      disabled={!editBody.trim() || editMutation.isPending}
                      onClick={() =>
                        editMutation.mutate({ path: { comment_id: comment.id }, body: { body: editBody } })
                      }
                      data-testid={`edit-comment-submit-${comment.id}`}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="px-4 py-3 text-sm text-foreground whitespace-pre-wrap break-words">{comment.body}</p>
              )}
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
            onClick={() => mutation.mutate({ path: { owner, repo, number }, body: { body } })}
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
