import cvxpy as cp
import torch
from cvxpylayers.torch import CvxpyLayer
from rotation_matrix_sdp import rotation_matrix_constraints
from convex_layers import *
import time
def make_rotation_matrix_sdp_layer():
    X = cp.Variable((10, 10), PSD=True)
    constraint_matrices, c_vec = rotation_matrix_constraints()
    constraints = [cp.trace(constraint_matrices[idx, :, :] @ X) == c_vec[idx]
                   for idx in range(constraint_matrices.shape[0])]
    A = cp.Parameter((10, 10), symmetric=True)
    prob = cp.Problem(cp.Minimize(cp.trace(A @ X)), constraints)
    return CvxpyLayer(prob, parameters=[A], variables=[X])


class RankOneHomogeneousMatrixExtractor(torch.autograd.Function):
    """
    Differentiable Rank-1 matrix extractor
    Input: BxNxN symmetric rank-1 tensor 'X'
    Output: BxN tensor 'x' s.t. X = x*x.T (outer product)
    """

    @staticmethod
    def forward(ctx, X):
        if X.dim() < 3:
            X = X.unsqueeze()
        eigvals, eigvecs = torch.symeig(X)
        nu_min, eigval_argmin = torch.min(eigvals, 1)  # , keepdim=False, out=None)
        x = eigvecs[torch.arange(X.shape[0]), :, eigval_argmin]
        x = x / (torch.sign(x[:, -1]).unsqueeze(1))
        ctx.save_for_backward(x, eigvals)

        return x

    @staticmethod
    def backward(ctx, grad_output):
        A, q, nu = ctx.saved_tensors
        grad_qcqp = compute_grad_fast(A, nu, q)
        outgrad = torch.einsum('bkq,bk->bq', grad_qcqp, grad_output)
        return outgrad

if __name__ == '__main__':

    # Sample code
    # n, m = 2, 3
    # x = cp.Variable(n)
    # A = cp.Parameter((m, n))
    # b = cp.Parameter(m)
    # constraints = [x >= 0]
    # objective = cp.Minimize(0.5 * cp.pnorm(A @ x - b, p=1))
    # problem = cp.Problem(objective, constraints)
    # assert problem.is_dpp()
    #
    # cvxpylayer = CvxpyLayer(problem, parameters=[A, b], variables=[x])
    # A_tch = torch.randn(m, n, requires_grad=True)
    # b_tch = torch.randn(m, requires_grad=True)
    #
    #
    # # solve the problem
    # solution, = cvxpylayer(A_tch, b_tch)
    #
    # # compute the gradient of the sum of the solution with respect to A, b
    # solution.sum().backward()
    
    num_samples = 1000
    sdp_rot_layer = make_rotation_matrix_sdp_layer()
    A_vec = torch.randn((num_samples, 55), dtype=torch.double, requires_grad=True)
    A =  convert_Avec_to_A(A_vec)

    start = time.time()
    Cmat = sdp_rot_layer(A)
    print('Solved {} SDPs in {:.3F} sec using cvxpylayers.'.format(num_samples, time.time() - start))


    start = time.time()
    r = HomogeneousRotationQCQPFastSolver.apply(A_vec)
    print('Solved {} SDPs in {:.3F} sec using custom solver.'.format(num_samples, time.time() - start))


    qcqp_solver = QuadQuatFastSolver.apply
    A_vec = torch.randn((num_samples, 10), dtype=torch.double, requires_grad=True)

    start = time.time()
    q = qcqp_solver(A_vec)
    print('Solved {} Quat QCQPs in {:.3F} sec.'.format(num_samples, time.time() - start))



