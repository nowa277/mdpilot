import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';
import { Button, IconButton, ScrollArea } from '@shared/ui';
import { cn, formatRelative } from '@shared/utils';
import { useNavigate, useParams } from 'react-router-dom';

import { useChatList, useCreateChat, useDeleteChat, useUpdateChat } from '../hooks/useChatList';

export function ChatList() {
  const { data: chats = [], isPending } = useChatList();
  const create = useCreateChat();
  const remove = useDeleteChat();
  const update = useUpdateChat();
  const navigate = useNavigate();
  const params = useParams<{ chatId?: string }>();
  const activeId = params.chatId;

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  function handleNew() {
    void create.mutateAsync({ title: '新会话' }).then((chat) => {
      navigate(`/workspace/c/${chat.id}`);
    });
  }

  function startEdit(chatId: string, currentTitle: string) {
    setEditingId(chatId);
    setEditTitle(currentTitle);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditTitle('');
  }

  function saveEdit(chatId: string) {
    if (editTitle.trim()) {
      update.mutate({ id: chatId, title: editTitle.trim() });
    }
    setEditingId(null);
    setEditTitle('');
  }

  return (
    <div className="flex h-full flex-col gap-2 p-3">
      <Button onClick={handleNew} disabled={create.isPending} className="glass-button">
        + New
      </Button>
      <ScrollArea className="flex-1">
        {isPending ? (
          <div className="px-2 py-3 text-xs text-text-3">Loading…</div>
        ) : chats.length === 0 ? (
          <div className="px-2 py-3 text-xs text-text-3">None</div>
        ) : (
          <ul className="flex flex-col gap-2">
         <AnimatePresence>
        {chats.map((chat) => (
                <motion.li
               key={chat.id}
             initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
               transition={{ duration: 0.2 }}
               className="group flex items-center gap-1"
          >
                  {editingId === chat.id ? (
           <div className="glass-card flex flex-1 items-center gap-1 px-2 py-2">
                  <input
              type="text"
                      value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => {
                if (e.key === 'Enter') saveEdit(chat.id);
                    if (e.key === 'Escape') cancelEdit();
                      }}
                        className="glass-input flex-1 px-2 py-1 text-sm"
                        autoFocus
                      />
              <IconButton
                aria-label="保存"
                   onClick={() => saveEdit(chat.id)}
                  className="text-primary-green"
            >
                   ✓
               </IconButton>
             <IconButton
                      aria-label="取消"
                    onClick={cancelEdit}
                     className="text-text-3"
                   >
                   ×
                      </IconButton>
             </div>
                  ) : (
                <>
                 <button
                        onClick={() => navigate(`/workspace/c/${chat.id}`)}
                        className={cn(
                          'glass-card flex flex-1 flex-col px-3 py-2.5 text-left text-sm transition-all duration-200',
                        activeId === chat.id
                       ? 'border-primary-cyan/50 bg-primary-cyan/10 text-text-1 shadow-glow-cyan'
                            : 'text-text-2 hover:border-border-2',
                   )}
                >
                <span className="truncate font-medium">{chat.title}</span>
                   <span className="text-xs text-text-3">
                    {formatRelative(new Date(chat.updatedAt).getTime())}
               </span>
                      </button>
                <IconButton
                      aria-label={`编辑会话 ${chat.title}`}
                  onClick={() => startEdit(chat.id, chat.title)}
                className="opacity-0 transition-opacity duration-200 group-hover:opacity-100"
                      >
                ✎
                      </IconButton>
           <IconButton
                        aria-label={`删除会话 ${chat.title}`}
                        onClick={() => remove.mutate(chat.id)}
                        className="opacity-0 transition-opacity duration-200 group-hover:opacity-100"
                      >
                    ×
                  </IconButton>
                    </>
               )}
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </ScrollArea>
    </div>
  );
}
