import { ReadProductDto } from 'src/product/dto/read-product-dto';

export interface CreateResultDto extends Omit<ReadProductDto, 'id'> {}
