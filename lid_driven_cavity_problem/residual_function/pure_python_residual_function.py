def residual_function(X, graph):
    '''
    Pure Python (non-vectorized) implementation of the residual function (coupled).
    Will solve the three equations on order:

    1- Conservation of mass (Equations for P)
    2- Navier Stokes in X   (Equations for U)
    2- Navier Stokes in Y   (Equations for V)

    The X vector must have the following format:

    [P0, U0, V0, ... Pn, Un, Vn]

    The equations must be built in the following order, then:

    CM_0
    NS-X_0
    NS-Y_0
    : : :
    CM_n
    NS-X_n
    NS-Y_n
    '''
    pressure_mesh = graph.pressure_mesh
    ns_x_mesh = graph.ns_x_mesh
    ns_y_mesh = graph.ns_y_mesh

    # Initialize all residuals with None (Should NOT initialize with zeros, so that we can make a
    # sanity check in the end of this function!)
    residual = [None] * (len(X))

    # Knowns (Constants)
    dt = graph.dt
    dx = graph.dx
    dy = graph.dy
    rho = graph.rho
    mi = graph.mi
    bc = graph.bc  # Velocity at the top (U_top)

    # Extract unknown vectors from the full X vector
    # TODO: Drop numpy implementation to use pure-python
    #
    import numpy as np
    # Pressure
    P = X[0::3]
    # Velocity in X. Note that there are some dummy velocities, in order to keep the same size on
    # all equations.
    extended_U = X[1::3]
    nx = graph.ns_x_mesh.nx
    ny = graph.ns_x_mesh.ny
    U_idxs = np.arange(0, len(graph.ns_x_mesh)) + np.repeat(np.arange(0, ny), nx)
    U = extended_U[U_idxs]
    V = X[2::3][0:len(ns_y_mesh)]

    for i in range(len(pressure_mesh)):
        j = i // pressure_mesh.nx

        # Index conversion
        i_U_w = i - j - 1
        i_U_e = i_U_w + 1
        i_V_n = i
        i_V_s = i_V_n - pressure_mesh.nx

        # Knowns
        is_left_boundary = i % pressure_mesh.nx == 0
        is_right_boundary = (i + 1) % pressure_mesh.nx == 0
        is_bottom_boundary = j % pressure_mesh.ny == 0
        is_top_boundary = (j + 1) % pressure_mesh.ny == 0

        # Unknowns
        U_w = 0.0 if is_left_boundary else U[i_U_w]
        U_e = 0.0 if is_right_boundary else U[i_U_e]
        V_n = 0.0 if is_top_boundary else V[i_V_n]
        V_s = 0.0 if is_bottom_boundary else V[i_V_s]

        # Conservation of Mass
        ii = 3 * i
        residual[ii] = (U_e * dy - U_w * dy) + (V_n * dx - V_s * dx)

    for i in range(len(ns_x_mesh)):
        j = i // ns_x_mesh.nx

        # Index conversion
        i_U_P = i
        i_U_W = i - 1
        i_U_E = i + 1
        i_U_N = i + ns_x_mesh.nx
        i_U_S = i - ns_x_mesh.nx
        i_P_w = i + (i // ns_x_mesh.nx)
        i_P_e = i_P_w + 1
        i_V_NW = i + j
        i_V_NE = i_V_NW + 1
        i_V_SW = i_V_NW - ns_y_mesh.nx
        i_V_SE = i_V_NE - ns_y_mesh.nx

        # Knowns
        U_P_old = ns_x_mesh.phi_old[i_U_P]
        is_left_boundary = i % ns_x_mesh.nx == 0
        is_right_boundary = (i + 1) % ns_x_mesh.nx == 0
        is_bottom_boundary = j % ns_x_mesh.ny == 0
        is_top_boundary = (j + 1) % ns_x_mesh.ny == 0

        # Unknowns
        U_P = U[i_U_P]
        U_W = 0.0 if is_left_boundary else U[i_U_W]
        U_E = 0.0 if is_right_boundary else U[i_U_E]
        U_N = bc if is_top_boundary else U[i_U_N]
        U_S = 0.0 if is_bottom_boundary else U[i_U_S]
        P_w = P[i_P_w]
        P_e = P[i_P_e]
        V_NE = 0.0 if is_top_boundary else V[i_V_NE]
        V_NW = 0.0 if is_top_boundary else V[i_V_NW]
        V_SE = 0.0 if is_bottom_boundary else V[i_V_SE]
        V_SW = 0.0 if is_bottom_boundary else V[i_V_SW]

        # Calculated (Interpolated and Secondary Variables)
        dU_e_dx = (U_E - U_P) / dx
        dU_w_dx = (U_P - U_W) / dx
        dU_n_dx = (U_N - U_P) / dy
        dU_s_dx = (U_P - U_S) / dy
        U_e = (U_E + U_P) / 2.0
        U_w = (U_P + U_W) / 2.0
        V_n = (V_NE + V_NW) / 2.0
        V_s = (V_SE + V_SW) / 2.0
        beta_U_e = 0.5 if U_e > 0.0 else -0.5
        beta_U_w = 0.5 if U_w > 0.0 else -0.5
        beta_V_n = 0.5 if V_n > 0.0 else -0.5
        beta_V_s = 0.5 if V_s > 0.0 else -0.5

        # Navier Stokes X
        transient_term = (rho * U_P - rho * U_P_old) * (dx * dy / dt)
        advective_term = \
            rho * U_e * ((.5 - beta_U_e) * U_E + (.5 + beta_U_e) * U_P) * dy - \
            rho * U_w * ((.5 - beta_U_w) * U_P + (.5 + beta_U_w) * U_W) * dy + \
            rho * V_n * ((.5 - beta_V_n) * U_N + (.5 + beta_V_n) * U_P) * dx - \
            rho * V_s * ((.5 - beta_V_s) * U_P + (.5 + beta_V_s) * U_S) * dx
        difusive_term = \
            mi * dU_e_dx * dy - \
            mi * dU_w_dx * dy + \
            mi * dU_n_dx * dx - \
            mi * dU_s_dx * dx
        source_term = -(P_e - P_w) * dy

        U_idxs = np.arange(0, len(graph.ns_x_mesh)) + np.repeat(np.arange(0, ny), nx)
        ii = 3 * U_idxs[i] + 1
        residual[ii] = transient_term + advective_term - difusive_term - source_term

    for i in range(len(ns_y_mesh)):
        j = i // ns_y_mesh.nx

        # Index conversion
        i_V_P = i
        i_V_W = i - 1
        i_V_E = i + 1
        i_V_N = i + ns_y_mesh.nx
        i_V_S = i - ns_y_mesh.nx
        i_P_n = i + ns_y_mesh.nx
        i_P_s = i
        i_U_SE = i - j
        i_U_SW = i_U_SE - 1
        i_U_NE = i_U_SE + ns_x_mesh.nx
        i_U_NW = i_U_SW + ns_x_mesh.nx

        # Knowns
        V_P_old = ns_y_mesh.phi_old[i_V_P]
        is_left_boundary = i % ns_y_mesh.nx == 0
        is_right_boundary = (i + 1) % ns_y_mesh.nx == 0
        is_bottom_boundary = j % ns_y_mesh.ny == 0
        is_top_boundary = (j + 1) % ns_y_mesh.ny == 0

        # Unknowns
        V_P = V[i_V_P]
        V_E = 0.0 if is_right_boundary else V[i_V_E]
        V_W = 0.0 if is_left_boundary else V[i_V_W]
        V_N = 0.0 if is_top_boundary else V[i_V_N]
        V_S = 0.0 if is_bottom_boundary else V[i_V_S]
        P_n = P[i_P_n]
        P_s = P[i_P_s]
        U_SE = 0.0 if is_right_boundary else U[i_U_SE]
        U_SW = 0.0 if is_left_boundary else U[i_U_SW]
        U_NE = 0.0 if is_right_boundary else bc if is_top_boundary else U[i_U_NE]
        U_NW = 0.0 if is_left_boundary else bc if is_top_boundary else U[i_U_NW]

        # Calculated (Interpolated and Secondary Variables)
        dV_e_dx = (V_E - V_P) / dx
        dV_w_dx = (V_P - V_W) / dx
        dV_n_dx = (V_N - V_P) / dy
        dV_s_dx = (V_P - V_S) / dy
        U_e = (U_NE + U_SE) / 2.0
        U_w = (U_NW + U_SW) / 2.0
        V_n = (V_P + V_N) / 2.0
        V_s = (V_S + V_P) / 2.0
        beta_U_e = 0.5 if U_e > 0.0 else -0.5
        beta_U_w = 0.5 if U_w > 0.0 else -0.5
        beta_V_n = 0.5 if V_n > 0.0 else -0.5
        beta_V_s = 0.5 if V_s > 0.0 else -0.5

        # Navier Stokes Y
        transient_term = (rho * V_P - rho * V_P_old) * (dx * dy / dt)
        advective_term = \
            rho * U_e * ((.5 - beta_U_e) * V_E + (.5 + beta_U_e) * V_P) * dy - \
            rho * U_w * ((.5 - beta_U_w) * V_P + (.5 + beta_U_w) * V_W) * dy + \
            rho * V_n * ((.5 - beta_V_n) * V_N + (.5 + beta_V_n) * V_P) * dx - \
            rho * V_s * ((.5 - beta_V_s) * V_P + (.5 + beta_V_s) * V_S) * dx
        difusive_term = \
            mi * dV_e_dx * dy - \
            mi * dV_w_dx * dy + \
            mi * dV_n_dx * dx - \
            mi * dV_s_dx * dx
        source_term = -(P_n - P_s) * dy

        ii = 3 * i + 2
        residual[ii] = transient_term + advective_term - difusive_term - source_term

    # Set all remaining residuals with x[i] - x[i] = R
    # Basically, will avoid None on equations for U_dummy that have no equation attached.
    #
    for ii in range(len(X)):
        if residual[ii] is None:
            residual[ii] = X[ii]

    # Sanity check
    assert None not in residual, 'Missing equation in residual function'

    return residual
