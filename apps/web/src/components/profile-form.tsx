'use client';
import { useState, type FormEvent } from 'react';
import { Heading, useUiReady } from './portal-shell';
export function ProfileForm() {
  const ready = useUiReady();
  const [notice, setNotice] = useState('');
  function validate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setNotice(['business', 'contact', 'email'].every(key => String(data.get(key) ?? '').trim()) ?
      'Basic fields are complete. This is not a verified seller profile; nothing was saved.' : 'Enter a business name, contact name and business email to review the local draft.');
  }
  return <><Heading kicker="SELLER / BUSINESS SETUP" title="Introduce your business." description="Prepare real business information for future verification. No seller account or profile is created here." />
    <form className="form-section profile-form" onSubmit={validate}>
      <div className="field-grid"><label><span>Business name *</span><input name="business" required maxLength={160} /></label><label><span>Contact name *</span><input name="contact" required maxLength={160} /></label>
        <label><span>Business email *</span><input name="email" required type="email" maxLength={254} /></label><label><span>Business website</span><input name="website" type="url" maxLength={2048} /></label></div>
      <label><span>About your business</span><textarea name="about" rows={5} maxLength={2000} /></label>
      <p className="footnote">Do not enter passwords, bank details, identity documents or payment credentials. This draft is held only on this page.</p>
      <div className="button-row"><button className="button primary" type="submit" disabled={!ready}>Review local draft</button><button className="button secondary" disabled type="button">Save profile · unavailable</button></div>
      <noscript>JavaScript is required for local draft review. This form cannot be submitted.</noscript>
      <p role="status">{notice}</p>
    </form></>;
}
