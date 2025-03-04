import torch
import torch.nn as nn

# ------------------------------------------------------------------------------------- #


def infer(net, t, x, conds, mask, guidance_weight):
    bs = x.shape[0]

    if conds is None:
        x_out = net(t.expand(bs), x, mask=mask)[0]
        return x_out

    x_both = torch.cat([x, x])
    cond_knot = torch.zeros_like(conds)
    y_both = torch.cat([conds, cond_knot])
    mask_both = torch.cat([mask, mask])
    t_both = torch.cat([t.expand(bs), t.expand(bs)])

    out = net(t_both, x_both, y=y_both, mask=mask_both)[0]
    cond_denoised, uncond_denoised = out.chunk(2)
    x_out = uncond_denoised + (cond_denoised - uncond_denoised) * guidance_weight

    return x_out


# ------------------------------------------------------------------------------------- #


class DDPMSampler(nn.Module):
    def __init__(self, scheduler: nn.Module, num_steps: int, cfg_rate: float, **kwargs):
        super().__init__()
        self.scheduler = scheduler
        self.num_steps = num_steps
        self.cfg_rate = cfg_rate

    def sample(
        self,
        net,
        latents: torch.Tensor,
        conds: torch.Tensor = None,
        mask: torch.Tensor = None,
        randn_like=torch.randn_like,
    ):
        # Time step discretization
        step_indices = torch.arange(self.num_steps + 1, device=latents.device)
        t_steps = 1 - step_indices / self.num_steps
        gammas = self.scheduler(t_steps)

        # Main sampling loop
        bool_mask = ~mask.to(bool)
        x_cur = latents
        for step, (g_cur, g_next) in enumerate(zip(gammas[:-1], gammas[1:])):
            x0 = infer(net, g_cur, x_cur, conds, bool_mask, self.cfg_rate)

            log_alpha_cur = torch.log(g_cur) - torch.log(g_next)
            alpha_cur = torch.clip(torch.exp(log_alpha_cur), 0, 1)

            # x0 prediction (g --> \bar{alpha})
            # ------------------------------------------------------------------------- #
            # Complete this part for `Code 7`
            # x_mean = ...
            # var_t = ...
            # x_next = ...
            # ------------------------------------------------------------------------- #

            x_mean = torch.sqrt(alpha_cur) * (1 - g_next) / (1 - g_cur) * x_cur + torch.sqrt(g_next) * (1 - alpha_cur) / (1 - g_cur) * x0  # Compute x_mean for the next step

            var_t = (1 - g_next) * (1 - alpha_cur) / (1 - g_cur)  # Compute the variance

            # Sample noise from standard normal distribution and adjust with sqrt(var_t)
            noise = randn_like(x_cur) * torch.sqrt(var_t)

            # Compute the next step sample (x_next)
            x_next = x_mean + noise

            x_cur = x_next

        return x_cur
