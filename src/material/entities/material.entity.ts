import { Product } from 'src/product/entities/product.entity';
import {
  Column,
  Entity,
  JoinColumn,
  ManyToOne,
  PrimaryGeneratedColumn,
} from 'typeorm';

@Entity('material', { schema: 'public' })
export class Material {
  @PrimaryGeneratedColumn({ type: 'integer', name: 'id' })
  id: number;

  @Column('integer', { name: 'product_id' })
  product_id: number;

  @Column('varchar', { name: 'name', length: 255 })
  name: string;

  @Column('boolean', { name: 'basic' })
  basic: boolean;

  @Column('float', { name: 'count' })
  count: number;

  @ManyToOne(() => Product, (product) => product)
  @JoinColumn([{ name: 'product_id', referencedColumnName: 'id' }])
  product: Product;
}
