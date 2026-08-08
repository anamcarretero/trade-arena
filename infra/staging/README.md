# IaC de staging

Este módulo define únicamente staging: Artifact Registry, API y migración en
Cloud Run, IAM/OIDC, nombres de Secret Manager, habilitación e identidad de
Scheduler, Neon Frankfurt y proyecto/custom environment Vercel. No crea jobs
financieros, dominios ni producción.

Los proveedores leen credenciales exclusivamente del entorno:
`GOOGLE_APPLICATION_CREDENTIALS`/ADC durante el bootstrap, `NEON_API_KEY` y
`VERCEL_API_TOKEN`. Los valores de aplicación se cargan fuera de Terraform para
que no entren en Git ni en el estado. Consulta `doc/instalacion-despliegue.md`.

Validación sin credenciales ni creación de recursos:

```bash
terraform -chdir=infra/staging fmt -check -recursive
terraform -chdir=infra/staging init -backend=false
terraform -chdir=infra/staging validate
```

Un `plan` real necesita proyecto, cuentas y tokens existentes. Un `apply`
puede crear recursos facturables y requiere autorización explícita.

El bootstrap es deliberadamente bifásico. Con `deploy_runtime=false` crea los
cimientos y nombres de secretos. Después se cargan versiones, se publica
`Dockerfile` mediante `scripts/staging/publish-image.sh`, se fija su digest y se
aplica con `deploy_runtime=true`. Así nunca se usa una imagen alternativa ni se
intenta arrancar un runtime sin secretos.
