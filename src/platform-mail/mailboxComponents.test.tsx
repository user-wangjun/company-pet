import { createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { LetterReader } from "./LetterReader";
import { MailboxPanel } from "./MailboxPanel";
import {
  BUILT_IN_LETTERS,
  EMPTY_MAILBOX_STATE,
  WELCOME_LETTER_ID,
  markLetterRead,
} from "./mailbox";

describe("mailbox components", () => {
  test("renders mailbox list with unread count and permanent welcome letter", () => {
    const html = renderToStaticMarkup(
      <MailboxPanel
        letters={BUILT_IN_LETTERS}
        state={EMPTY_MAILBOX_STATE}
        onClose={vi.fn()}
        onDeleteRead={vi.fn()}
        onMarkAllRead={vi.fn()}
        onOpenLetter={vi.fn()}
      />,
    );

    expect(html).toContain("role=\"dialog\"");
    expect(html).toContain("信箱");
    expect(html).toContain("未读 1");
    expect(html).toContain("致初次相遇的您");
    expect(html).toContain("望星科技 × 知了");
    expect(html).toContain("永久保留");
    expect(html).toContain("未读");
  });

  test("disables bulk actions when every visible letter is read and permanent", () => {
    const readState = markLetterRead(EMPTY_MAILBOX_STATE, WELCOME_LETTER_ID);
    const html = renderToStaticMarkup(
      <MailboxPanel
        letters={BUILT_IN_LETTERS}
        state={readState}
        onClose={vi.fn()}
        onDeleteRead={vi.fn()}
        onMarkAllRead={vi.fn()}
        onOpenLetter={vi.fn()}
      />,
    );

    expect(html).toContain("disabled=\"\"");
    expect(html).toContain("已读");
    expect(html).toContain("未读 0");
  });

  test("renders first-use sealed envelope with the wax seal", () => {
    const html = renderToStaticMarkup(
      <LetterReader
        letter={BUILT_IN_LETTERS[0]}
        mailboxTargetRef={createRef<HTMLButtonElement>()}
        mode="first-use"
        onRead={vi.fn()}
        onStored={vi.fn()}
      />,
    );

    expect(html).toContain("letter-overlay is-sealed");
    expect(html).toContain("点击任意位置拆信");
    expect(html).toContain("letter-wax-seal");
    expect(html).toContain("愈");
  });

  test("renders mailbox-opened letter directly as readable paper", () => {
    const html = renderToStaticMarkup(
      <LetterReader
        letter={BUILT_IN_LETTERS[0]}
        mailboxTargetRef={createRef<HTMLButtonElement>()}
        mode="mailbox"
        onRead={vi.fn()}
        onStored={vi.fn()}
      />,
    );

    expect(html).toContain("letter-overlay is-open");
    expect(html).toContain("aria-label=\"关闭信件\"");
    expect(html).toContain("致初次相遇的您");
    expect(html).toContain("所以，来领养一只桌宠吧！");
    expect(html).not.toContain("点击任意位置拆信");
  });
});
