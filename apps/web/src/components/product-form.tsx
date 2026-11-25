'use client';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { imageFileError, validateProductDraft } from '../presentation/form-policy';
import { Heading, useUiReady } from './portal-shell';

function Input({ name, label, required = true, type = 'text', help, maxLength = 240 }: { name: string; label: string; required?: boolean; type?: string; help?: string; maxLength?: number }) {
  return <label><span>{label}{required && <small> *</small>}</span><input name={name} type={type} required={required} maxLength={maxLength} aria-describedby={help ? name + '-help' : undefined} />
    {help && <small id={name + '-help'}>{help}</small>}</label>;
}
type Preview = { title: string; brand: string; description: string; variants: { size: string; color: string; price: string }[] };
export function ProductForm({ seller = false }: { seller?: boolean }) {
  const ready = useUiReady();
  const [variants, setVariants] = useState([0]), nextId = useRef(1);
  const [errors, setErrors] = useState<string[]>([]), [preview, setPreview] = useState<Preview | null>(null);
  const [image, setImage] = useState<string | null>(null), [fileError, setFileError] = useState('');
  const [imageName, setImageName] = useState('');
  const feedback = useRef<HTMLDivElement>(null);
  useEffect(() => () => { if (image) URL.revokeObjectURL(image); }, [image]);
  function validate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget), read = (key: string) => String(data.get(key) ?? '').trim();
    const fields = Object.fromEntries(Array.from(data.entries()).filter((entry): entry is [string, string] => typeof entry[1] === 'string'));
    const issues = validateProductDraft(fields, variants, !!image, fileError);
    const rows = variants.map(id => {
      return { size: read('size-' + id), color: read('color-' + id), price: read('price-' + id) };
    });
    setErrors(issues);
    setPreview(issues.length ? null : { title: read('title'), brand: read('brand'), description: read('description'), variants: rows });
    requestAnimationFrame(() => feedback.current?.focus());
  }
  return <>
    <Heading kicker={seller ? 'SELLER / PREPARE SUBMISSION' : 'ADMIN / PRODUCT EDITOR'} title={seller ? 'Tell the product’s story.' : 'Make every detail count.'}
      description="Work with real information. Validate and preview on this page; nothing is uploaded, saved or published." />
    <form className="editor-grid" onSubmit={validate} noValidate onChange={() => { setPreview(null); setErrors([]); }}>
      <div className="form-stack">
        <section className="form-section"><div className="section-title"><h2><span>01</span> Product identity</h2><span>REQUIRED FIELDS *</span></div>
          <div className="field-grid"><Input name="title" label="Product title" /><Input name="brand" label="Brand" />
            <Input name="category" label="Category" help="Use the source’s category; the approved taxonomy is pending." /><Input name="keywords" label="Keywords" required={false} help="Comma-separated attributes from the real product." />
          </div>
          <label><span>Description</span><textarea name="description" maxLength={4000} rows={4} /></label>
        </section>
        <section className="form-section"><h2><span>02</span> Merchant & source</h2><div className="field-grid">
          <Input name="merchant" label="Merchant/source" /><Input name="source" label="Source record reference" />
          <Input name="destination" label="Retailer destination" type="url" maxLength={2048} help="HTTPS. No link will open from this preview; approved hosts require review." />
          <Input name="approver" label="Rights/source approver reference" help="Reference only. This does not appoint or authenticate an approver." />
        </div></section>
        <section className="form-section"><h2><span>03</span> Variants & source prices</h2><p className="footnote">Unknown size/color stays unknown. Price is tax-inclusive INR from source evidence. Inventory is not inferred.</p>
          {variants.map((id, i) => <fieldset key={id} className="variant"><legend>Variant {i + 1}</legend><div className="field-grid">
            <Input name={'sku-' + id} label="Source variant key" /><Input name={'size-' + id} label="Size" required={false} />
            <Input name={'color-' + id} label="Color" required={false} /><Input name={'price-' + id} label="Price (INR)" help="Exact rupees, up to two decimal places. No discounts inferred." />
            <Input name={'observed-' + id} label="Source observation (local time)" type="datetime-local" /><Input name={'until-' + id} label="Valid until (local time)" type="datetime-local" />
          </div><p className="footnote">Inventory: unknown · Price freshness policy requires review.</p>
            {variants.length > 1 && <button className="text-link" type="button" onClick={() => { setVariants(variants.filter(item => item !== id)); setPreview(null); }}>Remove this variant</button>}
          </fieldset>)}
          <button className="button secondary" type="button" disabled={variants.length >= 100} onClick={() => { setVariants([...variants, nextId.current++]); setPreview(null); }}>+ Add variant</button>
        </section>
        <section className="form-section"><h2><span>04</span> Images & permission</h2>
          <label className="upload"><span>Select a real product image</span><small>JPEG, PNG or WebP · up to 10 MiB · local preview only</small><input name="localImage" type="file" accept="image/jpeg,image/png,image/webp" onChange={event => {
            const file = event.target.files?.[0]; setImage(null); setImageName(''); setFileError('');
            if (!file) return; const issue = imageFileError(file.type, file.size);
            if (issue) { setFileError(issue); return; }
            setImage(URL.createObjectURL(file)); setImageName(file.name);
          }} /></label>
          {fileError && <p role="alert" className="error-text">{fileError}</p>}
          {image && <figure className="local-image">{/* Local object URL only; no remote fetch or upload. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={image} alt="Locally selected product preview, not approved or published" /><figcaption>{imageName} · local selection</figcaption>
          </figure>}
          <div className="field-grid"><Input name="imageUrl" label="Image source URL" required={false} type="url" maxLength={2048} help="Recorded as input only. Remote images are not fetched." /><Input name="alt" label="Image description / alt text" /></div>
          <label><span>Rights / permission evidence *</span><textarea name="rights" maxLength={2000} rows={3} aria-describedby="rights-help" /><small id="rights-help">Use a reference to approval evidence. Do not paste credentials, personal records or confidential license documents.</small></label>
          <label className="checkbox"><input name="rightsChecked" type="checkbox" />I have source evidence and permission for the content I entered. This still requires authorized review.</label>
          <p className="footnote">Each published color variant needs appropriate approved imagery. Variant-image assignment and rights enforcement await the authorized catalogue workflow.</p>
        </section>
      </div>
      <aside className="editor-aside">
        <section className="summary-panel"><p className="eyebrow">BEFORE IT GOES LIVE</p><h2>Prepare.<br />Review.<br />Publish with care.</h2><p>{seller ? 'Submissions require admin review. Sellers cannot directly publish to Discover.' : 'Source, image rights, variants and current prices all need approval before publication.'}</p>
          <ol><li>Complete real product information</li><li>Check the local draft preview</li><li>Connect the authorized review workflow</li></ol>
          <button className="button primary" type="submit" disabled={!ready}>Validate & preview draft</button>
          <noscript>JavaScript is required for local draft validation. This form cannot be submitted.</noscript>
          <button className="button secondary" type="button" disabled>{seller ? 'Submit for review · unavailable' : 'Save draft · unavailable'}</button>
          {!seller && <><button className="button secondary" type="button" disabled>Publish · unavailable</button><button className="button secondary" type="button" disabled>Withdraw · unavailable</button></>}
          <p className="footnote">No persistence. Leaving or reloading this page discards the draft. Client checks cannot approve rights or publication.</p>
        </section>
        <div ref={feedback} tabIndex={-1} className="validation-panel" aria-live="polite">
          {errors.length > 0 && <><h3>Check these details</h3><ul>{errors.map((error, i) => <li key={i}>{error}</li>)}</ul></>}
          {preview && <><p className="eyebrow">LOCAL DRAFT / NOT SAVED</p><h3>{preview.title}</h3><p>{preview.brand}</p><p>{preview.description}</p>
            {preview.variants.map((variant, i) => <p key={i}>{variant.size || 'Size unknown'} / {variant.color || 'Color unknown'} · INR {variant.price} (entered, unverified)</p>)}
            <p>Basic input checks completed. Source approval, taxonomy, host policy, price ceiling and freshness approval remain outstanding.</p></>}
          {!preview && !errors.length && <p>Local validation feedback and draft preview appear here.</p>}
        </div>
      </aside>
    </form>
  </>;
}
