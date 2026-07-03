# Real sample documents for testing

Download these public sample documents (blank templates / examples with no real
client PII) and drop the PDFs into this folder. Then upload them through the UI
or the API to test the pipeline on real-world layouts.

> These are third-party templates — kept out of git (see `.gitignore`). They are
> for local testing only.

## Spain (ES)

**Nota simple registral (title extract)**
- Idealista worked example (real layout): https://st3.idealista.com/static/es/pdf/shoppingcart/Ejemplo_de_Nota_Simple.pdf
- Registradores official portal (order a real one, ~€9): https://sede.registradores.org/site/propiedad
- Explanation + example: https://www.nota-simple.es/ejemplo-nota-simple-registro/

**Contrato de arrendamiento de local comercial (commercial lease)**
- Arquitasa template (PDF): https://arquitasa.com/wp-content/uploads/2022/02/modelo-contrato-alquiler-local-comercial_arquitasa.pdf
- Promein Abogados template (PDF): https://inmoweb.com/images/locnegopc.pdf
- Arrenta templates: https://www.arrenta.es/modelo-contrato-alquiler/

## France (FR)

**Bail commercial 3/6/9 (commercial lease)**
- SecuriBail template (PDF): https://www.abracadabrapdf.net/file/SecuriBail-Commercial369-SansFNIP.pdf
- Selectra (2026, Pinel-compliant): https://selectra.info/demenagement/contrat-bail/commercial
- BailPDF (2026): https://bailpdf.com/contrat-de-bail/commercial
- CreerEntreprise: https://www.creerentreprise.fr/modele-gratuit-bail-commercial-369/

## Rent roll / tenancy schedule
No standard public form — build one in Excel and export to PDF, or reuse the
synthetic one the demo generates. Columns the pipeline reads:
`Unit | Tenant | Use | Area m2 | Lease start | Lease end | Break date | Passing rent | Frequency | Index | Deposit | Arrears`

## How to test once downloaded

1. Put the PDFs in this folder.
2. Start the app (`make api` + `make web`), open http://localhost:5173.
3. Create a deal → upload the PDFs → the pipeline runs automatically.

Reality check: with the free offline mode (`DD_PROVIDER=local`) extraction on
these real layouts will be rough — it's tuned to the demo files. For a real test,
switch to the Mistral EU mode (see the main README "Provider modes" and the
`.env` file). OCR + citations + the audit log work in both modes.
